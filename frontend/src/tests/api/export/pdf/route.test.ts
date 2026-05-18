import { NextRequest } from 'next/server'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/serverToken', () => ({
    backendFetch: vi.fn(),
}))

vi.mock('@/lib/analytics/emitEvent.server', () => ({
    emitFromServer: vi.fn(() => Promise.resolve()),
}))

import { POST } from '@/app/api/export/pdf/[analysisId]/route'
import { emitFromServer } from '@/lib/analytics/emitEvent.server'
import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'
import type { AnalysisData } from '@/lib/types/api'

const mockBackendFetch = vi.mocked(backendFetch)
const mockEmitFromServer = vi.mocked(emitFromServer)

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

beforeEach(() => {
    vi.clearAllMocks()
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
