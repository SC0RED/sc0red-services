import { NextRequest } from 'next/server'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/serverToken', () => ({
    backendFetch: vi.fn(),
    getBackendToken: vi.fn(() => Promise.resolve('mock-id-token')),
}))

vi.mock('@/lib/analytics/emitEvent.server', () => ({
    emitFromServer: vi.fn(() => Promise.resolve()),
}))

vi.mock('next-auth/jwt', () => ({
    getToken: vi.fn(() => Promise.resolve({ orgId: 'org-1' })),
}))

vi.mock('next/headers', () => ({
    cookies: vi.fn(() => Promise.resolve({ getAll: () => [] })),
    headers: vi.fn(() =>
        Promise.resolve({
            entries: () => [].values(),
        })
    ),
}))

import { GET, POST } from '@/app/api/export/pdf/[analysisId]/route'
import { emitFromServer } from '@/lib/analytics/emitEvent.server'
import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'
import type { AnalysisData } from '@/lib/types/api'

const mockBackendFetch = vi.mocked(backendFetch)
const mockEmitFromServer = vi.mocked(emitFromServer)

const PDF_BYTES = new Uint8Array([0x25, 0x50, 0x44, 0x46]) // "%PDF"

function makeRequest(): NextRequest {
    return new NextRequest('http://localhost/api/export/pdf/assess-1')
}

const baseAnalysis: AnalysisData = {
    id: 'assess-1',
    companyName: 'Acme Corp',
    companyUrl: 'https://acme.test',
    industry: 'SaaS',
    overallRiskScore: 4.2,
    riskTier: 'moderate',
    analysisSummary: 'Example summary',
    analyzedAt: '2026-04-24T12:00:00.000Z',
    riskScores: [{ category: 'Data_Quality', score: 5, rationale: 'Some rationale' }],
    topActions: ['Action one'],
    opportunities: [
        {
            title: 'Deploy chatbot',
            description: 'A chatbot for support',
            impact_rating: 'High',
            timeline: 'Quick Win (1-3 months)',
            strategic_category: 'Competitive Moat',
            value_lever: 'Revenue Side',
            implementation_steps: ['Step 1'],
            investment_range: '$100K-$500K',
            roi_estimate: '30%',
        },
    ],
}

const ORIGINAL_FETCH = global.fetch

beforeEach(() => {
    vi.clearAllMocks()
    process.env.PDF_TOKEN_SECRET = 'test-secret-32-bytes-of-randomness-please'
    // Default fetch mock returns a successful PDF response from the Lambda.
    global.fetch = vi.fn().mockResolvedValue(
        new Response(PDF_BYTES, {
            status: 200,
            headers: { 'Content-Type': 'application/pdf' },
        })
    )
})

afterEach(() => {
    delete process.env.PDF_TOKEN_SECRET
    global.fetch = ORIGINAL_FETCH
})

describe('GET /api/export/pdf/[analysisId]', () => {
    it('returns binary PDF with the correct Content-Type and Content-Disposition', async () => {
        mockBackendFetch.mockResolvedValue(baseAnalysis)

        const response = await GET(makeRequest(), { params: { analysisId: 'assess-1' } })

        expect(response.status).toBe(200)
        expect(response.headers.get('content-type')).toBe('application/pdf')
        const disposition = response.headers.get('content-disposition') ?? ''
        expect(disposition).toContain('attachment;')
        expect(disposition).toContain('Acme Corp - AI Risk Report - 2026-04-24.pdf')
        expect(disposition).toContain('filename*=UTF-8')
        expect(response.headers.get('cache-control')).toBe('no-store')
    })

    it('emits sc0red_cta_rendered_in_pdf after successful render when opportunities exist', async () => {
        mockBackendFetch.mockResolvedValue(baseAnalysis)

        await GET(makeRequest(), { params: { analysisId: 'assess-1' } })

        expect(mockEmitFromServer).toHaveBeenCalledTimes(1)
        expect(mockEmitFromServer).toHaveBeenCalledWith('sc0red_cta_rendered_in_pdf', {
            analysisId: 'assess-1',
            opportunityCount: 1,
        })
    })

    it('does not emit when there are no opportunities (CTA is not rendered)', async () => {
        mockBackendFetch.mockResolvedValue({ ...baseAnalysis, opportunities: [] })

        await GET(makeRequest(), { params: { analysisId: 'assess-1' } })

        expect(mockEmitFromServer).not.toHaveBeenCalled()
    })

    it('does not wait for emitFromServer before returning the PDF', async () => {
        mockBackendFetch.mockResolvedValue(baseAnalysis)
        // A never-resolving emit would block the response if the route
        // awaited it. We assert the response arrives anyway — proving the
        // emit is fire-and-forget (`void`).
        mockEmitFromServer.mockReturnValueOnce(new Promise(() => {}))

        const response = await GET(makeRequest(), { params: { analysisId: 'assess-1' } })

        expect(response.status).toBe(200)
        expect(mockEmitFromServer).toHaveBeenCalled()
    })

    it('does not emit when the render Lambda errors', async () => {
        mockBackendFetch.mockResolvedValue(baseAnalysis)
        global.fetch = vi.fn().mockResolvedValue(new Response('err', { status: 500 }))

        const response = await GET(makeRequest(), { params: { analysisId: 'assess-1' } })

        expect(response.status).toBe(500)
        expect(mockEmitFromServer).not.toHaveBeenCalled()
    })

    it('returns 500 when the analysis fetch fails', async () => {
        mockBackendFetch.mockRejectedValue(new Error('upstream down'))

        const response = await GET(makeRequest(), { params: { analysisId: 'assess-1' } })

        expect(response.status).toBe(500)
        expect(mockEmitFromServer).not.toHaveBeenCalled()
    })

    it('passes a valid token to the render Lambda payload', async () => {
        mockBackendFetch.mockResolvedValue(baseAnalysis)
        const fetchMock = vi
            .fn()
            .mockResolvedValue(
                new Response(PDF_BYTES, { status: 200, headers: { 'Content-Type': 'application/pdf' } })
            )
        global.fetch = fetchMock

        await GET(makeRequest(), { params: { analysisId: 'assess-1' } })

        expect(fetchMock).toHaveBeenCalledTimes(1)
        const [, init] = fetchMock.mock.calls[0]
        const body = JSON.parse(init.body as string) as {
            analysisId: string
            token: string
            companyName: string
        }
        expect(body.analysisId).toBe('assess-1')
        expect(body.companyName).toBe('Acme Corp')
        // Token shape: base64url(payload).base64url(sig)
        expect(body.token.split('.')).toHaveLength(2)
    })
})

describe('POST /api/export/pdf/[analysisId]', () => {
    function makePostRequest(): NextRequest {
        return new NextRequest('http://localhost/api/export/pdf/assess-1', { method: 'POST' })
    }

    it('forwards 200 ready response from the backend (cached path)', async () => {
        mockBackendFetch.mockResolvedValue({
            status: 'ready',
            url: 'https://s3.example.com/pdf-exports/assess-1.pdf?sig=abc',
            generatedAt: '2026-05-18T10:00:13Z',
        })

        const response = await POST(makePostRequest(), { params: { analysisId: 'assess-1' } })

        expect(response.status).toBe(200)
        const body = (await response.json()) as { status: string; url: string }
        expect(body.status).toBe('ready')
        expect(body.url).toContain('s3.example.com')
        // Backend POST was called with the analysisId in the path.
        expect(mockBackendFetch).toHaveBeenCalledWith('/api/export/pdf/assess-1', {
            method: 'POST',
            body: {},
        })
    })

    it('forwards 202 rendering response from the backend (cold path)', async () => {
        mockBackendFetch.mockResolvedValue({
            status: 'rendering',
            startedAt: '2026-05-18T10:00:00Z',
        })

        const response = await POST(makePostRequest(), { params: { analysisId: 'assess-1' } })

        expect(response.status).toBe(202)
        const body = (await response.json()) as { status: string; startedAt: string }
        expect(body.status).toBe('rendering')
        expect(body.startedAt).toBe('2026-05-18T10:00:00Z')
    })

    it('emits sc0red_cta_rendered_in_pdf on the cached path when opportunities exist', async () => {
        // Cached path: 1st backendFetch is the POST → returns ready.
        // 2nd backendFetch is the analytics-driven analysis fetch.
        mockBackendFetch
            .mockResolvedValueOnce({
                status: 'ready',
                url: 'https://s3.example.com/pdf-exports/assess-1.pdf?sig=abc',
            })
            .mockResolvedValueOnce(baseAnalysis)

        await POST(makePostRequest(), { params: { analysisId: 'assess-1' } })

        expect(mockEmitFromServer).toHaveBeenCalledTimes(1)
        expect(mockEmitFromServer).toHaveBeenCalledWith('sc0red_cta_rendered_in_pdf', {
            analysisId: 'assess-1',
            opportunityCount: 1,
        })
    })

    it('does NOT emit when the cached analysis has zero opportunities', async () => {
        mockBackendFetch
            .mockResolvedValueOnce({
                status: 'ready',
                url: 'https://s3.example.com/pdf-exports/assess-1.pdf?sig=abc',
            })
            .mockResolvedValueOnce({ ...baseAnalysis, opportunities: [] })

        await POST(makePostRequest(), { params: { analysisId: 'assess-1' } })

        expect(mockEmitFromServer).not.toHaveBeenCalled()
    })

    it('does NOT emit on the cold path (rendering) — deferred to Phase 4', async () => {
        mockBackendFetch.mockResolvedValue({
            status: 'rendering',
            startedAt: '2026-05-18T10:00:00Z',
        })

        await POST(makePostRequest(), { params: { analysisId: 'assess-1' } })

        expect(mockEmitFromServer).not.toHaveBeenCalled()
    })

    it('still returns the cached PDF when the analytics fetch fails', async () => {
        // Analytics is best-effort — a failed analysis fetch must NOT
        // block the user's download.
        mockBackendFetch
            .mockResolvedValueOnce({
                status: 'ready',
                url: 'https://s3.example.com/pdf-exports/assess-1.pdf?sig=abc',
            })
            .mockRejectedValueOnce(new Error('analysis fetch failed'))

        const response = await POST(makePostRequest(), { params: { analysisId: 'assess-1' } })

        expect(response.status).toBe(200)
        const body = (await response.json()) as { status: string; url: string }
        expect(body.status).toBe('ready')
        expect(mockEmitFromServer).not.toHaveBeenCalled()
    })

    it('returns 500 when the backend signals a synchronous failure (status: failed)', async () => {
        mockBackendFetch.mockResolvedValue({
            status: 'failed',
            error: 'PDF export failed to enqueue',
        })

        const response = await POST(makePostRequest(), { params: { analysisId: 'assess-1' } })

        // HTTP code matches the failure semantics so access logs /
        // monitoring see the 5xx; client reads ``body.status`` anyway.
        expect(response.status).toBe(500)
        const body = (await response.json()) as { status: string; error: string }
        expect(body.status).toBe('failed')
        expect(body.error).toBe('PDF export failed to enqueue')
        // No analytics emission on the failure path.
        expect(mockEmitFromServer).not.toHaveBeenCalled()
    })

    it('propagates BackendError status (e.g., 404 not found, 401 unauthorized)', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('Not found', 404))

        const response = await POST(makePostRequest(), { params: { analysisId: 'missing' } })

        expect(response.status).toBe(404)
        const body = (await response.json()) as { error: string }
        expect(body.error).toBe('Not found')
    })

    it('returns 500 with the original error message on non-BackendError failures', async () => {
        mockBackendFetch.mockRejectedValue(new Error('upstream down'))

        const response = await POST(makePostRequest(), { params: { analysisId: 'assess-1' } })

        expect(response.status).toBe(500)
        const body = (await response.json()) as { error: string }
        expect(body.error).toBe('upstream down')
    })
})
