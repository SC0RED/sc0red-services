/**
 * Lambda entry point — dual-mode (sync + async).
 *
 * SYNC mode (existing, retired in Phase 4):
 *   Invoked via API Gateway proxy with `event.body = JSON.stringify({
 *     analysisId, token, frontendBaseUrl, companyName })`. Verifies the
 *   token, renders, returns the PDF as a base64 API Gateway response.
 *
 * ASYNC mode (new, primary entry point):
 *   Invoked via boto3 `InvocationType="Event"` with `event = {
 *     analysisId, s3Key, startedAt, companyName, token, frontendBaseUrl }`.
 *   No API Gateway wrapping. The Lambda renders, uploads the bytes to
 *   the per-analysis S3 key, then conditionally transitions the
 *   assessment record's PDF_EXPORT sub-row to `status=ready`. On any
 *   exception, best-effort writes `status=failed` + truncated error
 *   under the same `started_at` guard, then re-throws so Lambda's
 *   async-retry budget engages.
 *
 * Mode detection: an event with `s3Key` is async; everything else is
 * sync. The two modes share the token verification + Puppeteer render
 * but diverge sharply on output. See
 * `openspec/changes/async-pdf-export-with-cache/`.
 *
 * Emits structured JSON logs per render
 *   { event:'pdf_render', status:'ok'|'reject'|'error', ... }
 * preserved across both modes for the existing CloudWatch metric
 * filters (`pdf_render_construct.py:_build_metrics`).
 */

import type { APIGatewayProxyEventV2, APIGatewayProxyResultV2 } from 'aws-lambda'

import {
    markPdfExportFailed,
    markPdfExportReady,
    uploadPdfToS3,
} from './exportWriter'
import { PrintStatusError, renderPdf } from './render'
import { readSigningSecret } from './secretSource'
import { verifyToken } from './token'

const PDF_EXPORTS_BUCKET_ENV = 'PDF_EXPORTS_BUCKET'
const ASSESSMENT_TABLE_ENV = 'ASSESSMENT_TABLE'

interface RenderRequestBody {
    analysisId: string
    token: string
    frontendBaseUrl: string
    companyName: string
}

interface AsyncRenderEvent {
    analysisId: string
    s3Key: string
    startedAt: string
    companyName: string
    token: string
    frontendBaseUrl: string
}

type LambdaEvent = APIGatewayProxyEventV2 | AsyncRenderEvent | Record<string, unknown>

function isAsyncRenderEvent(event: LambdaEvent): event is AsyncRenderEvent {
    return typeof (event as { s3Key?: unknown }).s3Key === 'string'
}

function jsonResponse(status: number, body: unknown): APIGatewayProxyResultV2 {
    return {
        statusCode: status,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    }
}

function errorResponse(
    status: number,
    message: string,
    extra?: Record<string, unknown>,
): APIGatewayProxyResultV2 {
    return jsonResponse(status, { error: message, ...extra })
}

function buildPrintUrl(baseUrl: string, analysisId: string, token: string): string {
    const trimmedBase = baseUrl.replace(/\/$/, '')
    const encodedToken = encodeURIComponent(token)
    return `${trimmedBase}/print/${encodeURIComponent(analysisId)}?t=${encodedToken}`
}

function logEvent(detail: Record<string, unknown>): void {
    // Single-line JSON: CloudWatch metric filters can extract durationMs +
    // pdfSizeBytes without parsing the whole entry.
    console.log(JSON.stringify({ event: 'pdf_render', ...detail }))
}

export async function handler(event: LambdaEvent): Promise<APIGatewayProxyResultV2 | void> {
    if (isAsyncRenderEvent(event)) {
        return await handleAsyncRender(event)
    }
    return await handleSyncRender(event as APIGatewayProxyEventV2)
}

// ── Async mode (new, primary) ────────────────────────────────────────────────


async function handleAsyncRender(event: AsyncRenderEvent): Promise<void> {
    const startedAtMs = Date.now()
    const { analysisId, s3Key, startedAt, companyName, token, frontendBaseUrl } = event

    const bucket = process.env[PDF_EXPORTS_BUCKET_ENV]
    const tableName = process.env[ASSESSMENT_TABLE_ENV]
    if (!bucket || !tableName) {
        logEvent({
            status: 'error',
            reason: 'config',
            message: `${PDF_EXPORTS_BUCKET_ENV} and ${ASSESSMENT_TABLE_ENV} must be set`,
            analysisId,
        })
        // Re-throw so the async-invoke retry budget kicks in. The Python
        // POST handler has already written `status=rendering` to DDB; if
        // we exit silently here, the record stays rendering until the
        // stale-detection window (60 s).
        throw new Error('Async render misconfigured: missing env vars')
    }

    // Defensive token verification — the print route also verifies, but
    // failing fast here avoids spinning up Chromium for an obviously-bad
    // request.
    let secret: string
    try {
        secret = await readSigningSecret()
    } catch (error) {
        const message = error instanceof Error ? error.message : 'unknown'
        logEvent({ status: 'error', reason: 'config', message, analysisId })
        await failExport(tableName, analysisId, startedAt, `Secret resolution failed: ${message}`)
        throw error
    }
    const verification = verifyToken(token, analysisId, secret)
    if (!verification.ok) {
        logEvent({ status: 'reject', reason: verification.reason, analysisId, mode: 'async' })
        await failExport(tableName, analysisId, startedAt, `Token invalid: ${verification.reason}`)
        return
    }

    const printUrl = buildPrintUrl(frontendBaseUrl, analysisId, token)
    let pdfBytes: Buffer
    let renderMetrics: { durationMs: number; pageCount: number; pdfSizeBytes: number }
    try {
        const { pdf, metrics } = await renderPdf({ printUrl, companyName })
        pdfBytes = pdf
        renderMetrics = metrics
    } catch (error) {
        const reason = error instanceof PrintStatusError ? 'print_status' : 'render'
        const message = error instanceof Error ? error.message : 'Unknown render error'
        logEvent({
            status: 'error',
            reason,
            message,
            analysisId,
            mode: 'async',
            totalDurationMs: Date.now() - startedAtMs,
        })
        await failExport(tableName, analysisId, startedAt, message)
        // Re-throw so Lambda's async-invoke retry budget engages — the
        // configured DLQ catches exhausted retries.
        throw error
    }

    // Render succeeded — upload + transition to ready.
    try {
        await uploadPdfToS3({ bucket, key: s3Key, bytes: pdfBytes })
    } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown S3 error'
        logEvent({
            status: 'error',
            reason: 's3_put',
            message,
            analysisId,
            mode: 'async',
            totalDurationMs: Date.now() - startedAtMs,
        })
        await failExport(tableName, analysisId, startedAt, `S3 upload failed: ${message}`)
        throw error
    }

    const outcome = await markPdfExportReady({
        tableName,
        analysisId,
        s3Key,
        inputStartedAt: startedAt,
        generatedAt: new Date().toISOString(),
    })
    if (!outcome.ok) {
        // Conditional failure: another writer owns this record now
        // (re-analyse cleared the field, or a newer render is in flight).
        // The orphan S3 object is harmless — it'll be overwritten by
        // the next render of the same analysis. Log and exit cleanly.
        logEvent({
            status: outcome.reason === 'conditional_failed' ? 'reject' : 'error',
            reason: outcome.reason,
            message: outcome.message,
            analysisId,
            mode: 'async',
            totalDurationMs: Date.now() - startedAtMs,
        })
        return
    }

    logEvent({
        status: 'ok',
        analysisId,
        mode: 'async',
        durationMs: renderMetrics.durationMs,
        pageCount: renderMetrics.pageCount,
        pdfSizeBytes: renderMetrics.pdfSizeBytes,
        totalDurationMs: Date.now() - startedAtMs,
    })
}


async function failExport(
    tableName: string,
    analysisId: string,
    startedAt: string,
    error: string,
): Promise<void> {
    // Best-effort. If the conditional fails (no longer our row to write),
    // the next click re-triggers anyway via the stale-detection or the
    // failed-status branch — both POST-handler paths re-enqueue.
    //
    // The try/catch here is critical: callers that re-throw the original
    // render/S3 error rely on this function to NOT propagate its own
    // exceptions. Without the catch, a DDB throttle during the failed-
    // mark write would replace the original error (lost in CloudWatch)
    // and on the token-invalid path would trigger an async-invoke retry
    // for a deterministically-bad token. The original error has already
    // been logged at the call site; this log is a secondary signal for
    // operators investigating stuck-rendering records.
    try {
        const outcome = await markPdfExportFailed({
            tableName,
            analysisId,
            inputStartedAt: startedAt,
            error,
        })
        if (!outcome.ok) {
            console.log(
                JSON.stringify({
                    event: 'pdf_render',
                    status: 'error',
                    reason: 'fail_mark_outcome',
                    outcomeReason: outcome.reason,
                    outcomeMessage: outcome.message,
                    analysisId,
                }),
            )
        }
    } catch (markError) {
        console.log(
            JSON.stringify({
                event: 'pdf_render',
                status: 'error',
                reason: 'fail_mark_exception',
                message: markError instanceof Error ? markError.message : 'unknown',
                analysisId,
            }),
        )
    }
}


// ── Sync mode (legacy, retired in Phase 4) ──────────────────────────────────


type ParseResult =
    | { ok: true; parsed: { body: RenderRequestBody } }
    | { ok: false; status: number; message: string }


function parseSyncRequest(event: APIGatewayProxyEventV2): ParseResult {
    if (!event.body) {
        return { ok: false, status: 400, message: 'Request body is required' }
    }
    let parsed: Partial<RenderRequestBody>
    try {
        parsed = JSON.parse(event.body) as Partial<RenderRequestBody>
    } catch {
        return { ok: false, status: 400, message: 'Request body must be JSON' }
    }
    const required: (keyof RenderRequestBody)[] = [
        'analysisId',
        'token',
        'frontendBaseUrl',
        'companyName',
    ]
    for (const field of required) {
        if (typeof parsed[field] !== 'string' || !parsed[field]) {
            return { ok: false, status: 400, message: `Field "${field}" is required` }
        }
    }
    return { ok: true, parsed: { body: parsed as RenderRequestBody } }
}


async function handleSyncRender(event: APIGatewayProxyEventV2): Promise<APIGatewayProxyResultV2> {
    const startedAt = Date.now()

    const parseResult = parseSyncRequest(event)
    if (!parseResult.ok) {
        logEvent({ status: 'reject', reason: 'parse', message: parseResult.message })
        return errorResponse(parseResult.status, parseResult.message)
    }
    const { analysisId, token, frontendBaseUrl, companyName } = parseResult.parsed.body

    let secret: string
    try {
        secret = await readSigningSecret()
    } catch (error) {
        logEvent({
            status: 'error',
            reason: 'config',
            message: error instanceof Error ? error.message : 'unknown',
        })
        return errorResponse(500, 'Render Lambda misconfigured')
    }
    const verification = verifyToken(token, analysisId, secret)
    if (!verification.ok) {
        logEvent({ status: 'reject', reason: verification.reason, analysisId })
        return errorResponse(401, 'Invalid token', { reason: verification.reason })
    }

    const printUrl = buildPrintUrl(frontendBaseUrl, analysisId, token)
    try {
        const { pdf, metrics } = await renderPdf({ printUrl, companyName })
        logEvent({
            status: 'ok',
            analysisId,
            durationMs: metrics.durationMs,
            pageCount: metrics.pageCount,
            pdfSizeBytes: metrics.pdfSizeBytes,
            totalDurationMs: Date.now() - startedAt,
        })
        return {
            statusCode: 200,
            headers: { 'Content-Type': 'application/pdf' },
            isBase64Encoded: true,
            body: pdf.toString('base64'),
        }
    } catch (error) {
        if (error instanceof PrintStatusError) {
            logEvent({
                status: 'reject',
                reason: 'print_status',
                printStatus: error.status,
                analysisId,
                totalDurationMs: Date.now() - startedAt,
            })
            return errorResponse(401, 'Print page reported a non-ok status', {
                reason: error.status,
            })
        }
        const message = error instanceof Error ? error.message : 'Unknown render error'
        logEvent({
            status: 'error',
            reason: 'render',
            message,
            analysisId,
            totalDurationMs: Date.now() - startedAt,
        })
        return errorResponse(500, 'PDF render failed')
    }
}
