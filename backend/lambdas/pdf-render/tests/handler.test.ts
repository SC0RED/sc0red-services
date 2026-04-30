import type { APIGatewayProxyEventV2 } from 'aws-lambda'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { signToken } from '../src/token'

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

import { handler } from '../src/handler'
import { PrintStatusError, renderPdf } from '../src/render'
import { readSigningSecret } from '../src/secretSource'

const SECRET = 'test-secret-32-bytes-of-randomness-please'
const mockRender = vi.mocked(renderPdf)
const mockReadSigningSecret = vi.mocked(readSigningSecret)

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
