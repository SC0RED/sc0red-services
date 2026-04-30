import type { APIGatewayProxyEventV2 } from 'aws-lambda'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { signToken } from '../src/token'

// Mock the Puppeteer render so the handler tests don't try to launch
// Chromium. The mocked render returns a tiny "PDF" buffer so we can
// assert the Lambda's response shape.
vi.mock('../src/render', () => ({
    renderPdf: vi.fn(() =>
        Promise.resolve({
            pdf: Buffer.from('%PDF-mock-bytes'),
            metrics: { durationMs: 100, pageCount: 3, pdfSizeBytes: 16 },
        }),
    ),
}))

import { handler } from '../src/handler'
import { renderPdf } from '../src/render'

const SECRET = 'test-secret-32-bytes-of-randomness-please'
const mockRender = vi.mocked(renderPdf)

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
    process.env.PDF_TOKEN_SECRET = SECRET
})

afterEach(() => {
    delete process.env.PDF_TOKEN_SECRET
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

    it('returns 500 when PDF_TOKEN_SECRET is not set', async () => {
        delete process.env.PDF_TOKEN_SECRET
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
