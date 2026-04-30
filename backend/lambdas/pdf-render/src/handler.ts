/**
 * Lambda entry point.
 *
 * Receives an API Gateway proxy event with JSON body
 *   { analysisId, token, frontendBaseUrl, companyName }
 * Validates the token (defensive — the print route validates again),
 * launches Puppeteer via `render.ts`, returns the PDF buffer base64-
 * encoded for API Gateway binary support.
 *
 * Emits a structured JSON log line per render with
 *   { analysisId, durationMs, pageCount, pdfSizeBytes }
 * for capacity planning. Non-success paths log an `error` field; the
 * code itself never throws back to API Gateway — it returns 4xx/5xx
 * responses so the Next.js caller sees a stable error shape.
 */

import type { APIGatewayProxyEventV2, APIGatewayProxyResultV2 } from 'aws-lambda'

import { renderPdf } from './render'
import { readSigningSecret, verifyToken } from './token'

interface RenderRequestBody {
    analysisId: string
    token: string
    frontendBaseUrl: string
    companyName: string
}

interface ParsedRequest {
    body: RenderRequestBody
}

type ParseResult = { ok: true; parsed: ParsedRequest } | { ok: false; status: number; message: string }

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

function parseRequest(event: APIGatewayProxyEventV2): ParseResult {
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

function buildPrintUrl(baseUrl: string, analysisId: string, token: string): string {
    const trimmedBase = baseUrl.replace(/\/$/, '')
    const encodedToken = encodeURIComponent(token)
    return `${trimmedBase}/print/${encodeURIComponent(analysisId)}?t=${encodedToken}`
}

export async function handler(event: APIGatewayProxyEventV2): Promise<APIGatewayProxyResultV2> {
    const startedAt = Date.now()

    const parseResult = parseRequest(event)
    if (!parseResult.ok) {
        logEvent({ status: 'reject', reason: 'parse', message: parseResult.message })
        return errorResponse(parseResult.status, parseResult.message)
    }
    const { analysisId, token, frontendBaseUrl, companyName } = parseResult.parsed.body

    // Defensive token verification: the print route also verifies, but we
    // fail fast here to avoid spinning up Chromium for an obviously-bad
    // request. Saves ~2-3 seconds + container resources on misuse.
    let secret: string
    try {
        secret = readSigningSecret()
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

function logEvent(detail: Record<string, unknown>): void {
    // Single-line JSON: CloudWatch metric filters can extract durationMs +
    // pdfSizeBytes without parsing the whole entry.
    console.log(JSON.stringify({ event: 'pdf_render', ...detail }))
}
