import type { APIGatewayProxyEventV2 } from 'aws-lambda'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { signTokenForTest as signToken } from './helpers/signTokenForTest'

// Mock the Puppeteer render so the handler tests don't try to launch
// Chromium. The mocked render returns a tiny "PDF" buffer so we can
// assert the Lambda's response shape. `PrintStatusError` is re-exported
// from the actual module so handler tests can simulate the print-page-
// rejection branch without spinning up Chromium.
vi.mock('../src/render', async () => {
    const actual = await vi.importActual<typeof import('../src/render')>('../src/render')
    return {
        ...actual,
        renderPdf: vi.fn(() =>
            Promise.resolve({
                pdf: Buffer.from('%PDF-mock-bytes'),
                metrics: { durationMs: 100, pageCount: 3, pdfSizeBytes: 16 },
            }),
        ),
    }
})

// Mock the Secrets Manager fetch so handler tests don't hit AWS. The
// mock returns the test secret synchronously by default; tests that
// want to exercise the misconfig path override `mockResolvedValueOnce`
// or `mockRejectedValueOnce` per case.
vi.mock('../src/secretSource', () => ({
    readSigningSecret: vi.fn(),
    _resetSecretCacheForTests: vi.fn(),
}))

// Mock the S3 + DynamoDB writer surface so async-mode tests don't hit
// AWS. The default returns success; per-test overrides exercise the
// failure branches (S3 raises, conditional check fails, etc).
vi.mock('../src/exportWriter', () => ({
    uploadPdfToS3: vi.fn(),
    markPdfExportReady: vi.fn(),
    markPdfExportFailed: vi.fn(),
}))

import { handler } from '../src/handler'
import { markPdfExportFailed, markPdfExportReady, uploadPdfToS3 } from '../src/exportWriter'
import { PrintStatusError, renderPdf } from '../src/render'
import { readSigningSecret } from '../src/secretSource'

const SECRET = 'test-secret-32-bytes-of-randomness-please'
const mockRender = vi.mocked(renderPdf)
const mockReadSigningSecret = vi.mocked(readSigningSecret)
const mockUploadPdf = vi.mocked(uploadPdfToS3)
const mockMarkReady = vi.mocked(markPdfExportReady)
const mockMarkFailed = vi.mocked(markPdfExportFailed)

function buildEvent(body: unknown): APIGatewayProxyEventV2 {
    return {
        body: typeof body === 'string' ? body : JSON.stringify(body),
        version: '2.0',
        rawPath: '/api/admin/render-pdf',
        rawQueryString: '',
        headers: { 'content-type': 'application/json' },
        requestContext: {} as APIGatewayProxyEventV2['requestContext'],
        routeKey: 'POST /api/admin/render-pdf',
        isBase64Encoded: false,
    } as APIGatewayProxyEventV2
}

beforeEach(() => {
    vi.clearAllMocks()
    // Default: secret resolution succeeds with the test secret. Cases
    // that exercise the misconfig path override per-test.
    mockReadSigningSecret.mockResolvedValue(SECRET)
    // Defaults for async-mode tests — S3 + DDB both succeed.
    mockUploadPdf.mockResolvedValue(undefined)
    mockMarkReady.mockResolvedValue({ ok: true })
    mockMarkFailed.mockResolvedValue({ ok: true })
    // Required env vars for async-mode tests.
    process.env.PDF_EXPORTS_BUCKET = 'janus-test-pdf-exports'
    process.env.ASSESSMENT_TABLE = 'janus-test'
})

describe('PDF render Lambda handler', () => {
    it('returns 400 when the body is missing', async () => {
        const event = buildEvent('') as APIGatewayProxyEventV2
        // Force `body` to undefined to simulate API Gateway no-body case.
        ;(event as { body?: string }).body = undefined
        const response = (await handler(event)) as { statusCode: number; body: string }
        expect(response.statusCode).toBe(400)
    })

    it('returns 400 when the body is not JSON', async () => {
        const response = (await handler(buildEvent('not-json'))) as {
            statusCode: number
            body: string
        }
        expect(response.statusCode).toBe(400)
    })

    it('returns 400 when required fields are missing', async () => {
        const response = (await handler(
            buildEvent({ analysisId: 'a-1', token: 'x' }), // missing frontendBaseUrl + companyName
        )) as { statusCode: number; body: string }
        expect(response.statusCode).toBe(400)
        expect(JSON.parse(response.body).error).toMatch(/required/)
    })

    it('returns 401 when the token is invalid', async () => {
        const response = (await handler(
            buildEvent({
                analysisId: 'a-1',
                token: 'bad-token',
                frontendBaseUrl: 'https://example.com',
                companyName: 'Acme',
            }),
        )) as { statusCode: number; body: string }
        expect(response.statusCode).toBe(401)
        expect(mockRender).not.toHaveBeenCalled()
    })

    it('returns 401 when the token is for a different analysisId', async () => {
        const token = signToken({ analysisId: 'a-OTHER', orgId: 'org-1' }, SECRET)
        const response = (await handler(
            buildEvent({
                analysisId: 'a-1',
                token,
                frontendBaseUrl: 'https://example.com',
                companyName: 'Acme',
            }),
        )) as { statusCode: number; body: string }
        expect(response.statusCode).toBe(401)
        expect(mockRender).not.toHaveBeenCalled()
    })

    it('returns 200 with base64-encoded PDF on success', async () => {
        const token = signToken({ analysisId: 'a-1', orgId: 'org-1' }, SECRET)
        const response = (await handler(
            buildEvent({
                analysisId: 'a-1',
                token,
                frontendBaseUrl: 'https://example.com',
                companyName: 'Acme Corp',
            }),
        )) as {
            statusCode: number
            headers: Record<string, string>
            body: string
            isBase64Encoded: boolean
        }
        expect(response.statusCode).toBe(200)
        expect(response.headers['Content-Type']).toBe('application/pdf')
        expect(response.isBase64Encoded).toBe(true)
        // Round-trip through base64 to ensure the body is the rendered PDF.
        expect(Buffer.from(response.body, 'base64').toString()).toBe('%PDF-mock-bytes')
    })

    it('navigates to /print/{analysisId}?t=<token> on the configured base URL', async () => {
        const token = signToken({ analysisId: 'a-1', orgId: 'org-1' }, SECRET)
        await handler(
            buildEvent({
                analysisId: 'a-1',
                token,
                frontendBaseUrl: 'https://app.example.com/',
                companyName: 'Acme',
            }),
        )
        expect(mockRender).toHaveBeenCalledTimes(1)
        const [{ printUrl, companyName }] = mockRender.mock.calls[0]
        expect(printUrl).toBe(`https://app.example.com/print/a-1?t=${encodeURIComponent(token)}`)
        expect(companyName).toBe('Acme')
    })

    it('returns 401 (not 200 with junk PDF) when print page reports unauthorized', async () => {
        // Simulates the rotation / env-drift failure mode: the Lambda's
        // own `verifyToken` accepts the token (right secret) but the print
        // route rejects (wrong secret), so `verifyPrintStatus` throws.
        // Without the dedicated catch in `handler.ts`, this would silently
        // produce a 200 PDF of the "Unauthorized" page — see review-fixes PR.
        mockRender.mockRejectedValueOnce(new PrintStatusError('unauthorized'))
        const token = signToken({ analysisId: 'a-1', orgId: 'org-1' }, SECRET)
        const response = (await handler(
            buildEvent({
                analysisId: 'a-1',
                token,
                frontendBaseUrl: 'https://example.com',
                companyName: 'Acme',
            }),
        )) as { statusCode: number; body: string }
        expect(response.statusCode).toBe(401)
        const body = JSON.parse(response.body) as { reason?: string }
        expect(body.reason).toBe('unauthorized')
    })

    it('returns 401 when print page is missing the status marker entirely', async () => {
        // Belt-and-braces: a missing marker (page didn't render at all,
        // proxy error page, framework default) is also a fail-loud event.
        mockRender.mockRejectedValueOnce(new PrintStatusError('missing_marker'))
        const token = signToken({ analysisId: 'a-1', orgId: 'org-1' }, SECRET)
        const response = (await handler(
            buildEvent({
                analysisId: 'a-1',
                token,
                frontendBaseUrl: 'https://example.com',
                companyName: 'Acme',
            }),
        )) as { statusCode: number }
        expect(response.statusCode).toBe(401)
    })

    it('returns 500 when rendering throws', async () => {
        mockRender.mockRejectedValueOnce(new Error('chrome crashed'))
        const token = signToken({ analysisId: 'a-1', orgId: 'org-1' }, SECRET)
        const response = (await handler(
            buildEvent({
                analysisId: 'a-1',
                token,
                frontendBaseUrl: 'https://example.com',
                companyName: 'Acme',
            }),
        )) as { statusCode: number; body: string }
        expect(response.statusCode).toBe(500)
    })

    it('returns 500 when secret resolution fails (env or Secrets Manager)', async () => {
        mockReadSigningSecret.mockRejectedValueOnce(
            new Error('PDF_TOKEN_SECRET_ARN is not set on the PDF render Lambda runtime'),
        )
        const response = (await handler(
            buildEvent({
                analysisId: 'a-1',
                token: 'x',
                frontendBaseUrl: 'https://example.com',
                companyName: 'Acme',
            }),
        )) as { statusCode: number; body: string }
        expect(response.statusCode).toBe(500)
    })
})


describe('PDF render Lambda — async mode (S3 + DynamoDB)', () => {
    function asyncEvent(overrides: Record<string, unknown> = {}): Record<string, unknown> {
        const token = signToken({ analysisId: 'a-1', orgId: 'org-1' }, SECRET)
        return {
            analysisId: 'a-1',
            s3Key: 'pdf-exports/a-1.pdf',
            startedAt: '2026-05-18T10:00:00+00:00',
            companyName: 'Acme',
            token,
            frontendBaseUrl: 'https://app.example.com',
            ...overrides,
        }
    }

    it('uploads PDF + marks ready on the happy path', async () => {
        const result = await handler(asyncEvent())

        // Async mode returns void — async-invoke discards the value.
        expect(result).toBeUndefined()
        expect(mockUploadPdf).toHaveBeenCalledTimes(1)
        expect(mockUploadPdf).toHaveBeenCalledWith({
            bucket: 'janus-test-pdf-exports',
            key: 'pdf-exports/a-1.pdf',
            bytes: expect.any(Buffer),
        })
        expect(mockMarkReady).toHaveBeenCalledTimes(1)
        const readyArgs = mockMarkReady.mock.calls[0][0]
        expect(readyArgs.tableName).toBe('janus-test')
        expect(readyArgs.analysisId).toBe('a-1')
        expect(readyArgs.s3Key).toBe('pdf-exports/a-1.pdf')
        expect(readyArgs.inputStartedAt).toBe('2026-05-18T10:00:00+00:00')
        expect(readyArgs.generatedAt).toMatch(/^\d{4}-\d{2}-\d{2}T/)
        // No failed-marker on success.
        expect(mockMarkFailed).not.toHaveBeenCalled()
    })

    it('throws (engaging async-invoke retry) when bucket env var is missing', async () => {
        delete process.env.PDF_EXPORTS_BUCKET
        await expect(handler(asyncEvent())).rejects.toThrow(/misconfigured/)
        expect(mockUploadPdf).not.toHaveBeenCalled()
    })

    it('throws (engaging async-invoke retry) when table env var is missing', async () => {
        delete process.env.ASSESSMENT_TABLE
        await expect(handler(asyncEvent())).rejects.toThrow(/misconfigured/)
    })

    it('marks failed + returns void when token is invalid (does not retry)', async () => {
        // A bad token is a deterministic failure — retrying won't help,
        // so the handler logs + marks failed + returns cleanly (no throw).
        const result = await handler(asyncEvent({ token: 'bad-token' }))
        expect(result).toBeUndefined()
        expect(mockUploadPdf).not.toHaveBeenCalled()
        expect(mockMarkReady).not.toHaveBeenCalled()
        expect(mockMarkFailed).toHaveBeenCalledTimes(1)
        const failedArgs = mockMarkFailed.mock.calls[0][0]
        expect(failedArgs.error).toMatch(/Token invalid/)
    })

    it('marks failed + re-throws on render failure (so retry engages)', async () => {
        mockRender.mockRejectedValueOnce(new Error('chrome crashed'))
        await expect(handler(asyncEvent())).rejects.toThrow('chrome crashed')
        expect(mockMarkFailed).toHaveBeenCalledTimes(1)
        const failedArgs = mockMarkFailed.mock.calls[0][0]
        expect(failedArgs.error).toMatch(/chrome crashed/)
        expect(mockUploadPdf).not.toHaveBeenCalled()
        expect(mockMarkReady).not.toHaveBeenCalled()
    })

    it('marks failed + re-throws on S3 upload failure', async () => {
        mockUploadPdf.mockRejectedValueOnce(new Error('Access denied to bucket'))
        await expect(handler(asyncEvent())).rejects.toThrow('Access denied to bucket')
        expect(mockMarkFailed).toHaveBeenCalledTimes(1)
        const failedArgs = mockMarkFailed.mock.calls[0][0]
        expect(failedArgs.error).toMatch(/S3 upload failed/)
        expect(mockMarkReady).not.toHaveBeenCalled()
    })

    it('exits cleanly when conditional UpdateItem fails (race with re-analyse)', async () => {
        // A parallel re-analyse cleared the PDF_EXPORT row — our
        // `started_at` no longer matches, so the conditional fails.
        // The Lambda must NOT re-throw (no point retrying — re-analyse
        // is authoritative); instead it logs + exits.
        mockMarkReady.mockResolvedValueOnce({ ok: false, reason: 'conditional_failed' })
        const result = await handler(asyncEvent())
        expect(result).toBeUndefined()
        expect(mockUploadPdf).toHaveBeenCalledTimes(1)
        expect(mockMarkReady).toHaveBeenCalledTimes(1)
        expect(mockMarkFailed).not.toHaveBeenCalled()
    })

    it('detects async mode purely from the s3Key field, not event shape', async () => {
        // An object lacking `body` but containing `s3Key` is async — no
        // API Gateway wrapping. This is what `boto3.invoke(Payload=...)`
        // delivers.
        await handler(asyncEvent())
        expect(mockUploadPdf).toHaveBeenCalled()
    })
})
