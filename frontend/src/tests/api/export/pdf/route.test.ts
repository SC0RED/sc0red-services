import { NextRequest } from 'next/server'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/serverToken', () => ({
    backendFetch: vi.fn(),
}))

vi.mock('@/lib/analytics/emitEvent.server', () => ({
    emitFromServer: vi.fn(() => Promise.resolve()),
}))

import { GET } from '@/app/api/export/pdf/[analysisId]/route'
import { emitFromServer } from '@/lib/analytics/emitEvent.server'
import { backendFetch } from '@/lib/api/serverToken'
import type { AnalysisData } from '@/lib/types/api'

const mockBackendFetch = vi.mocked(backendFetch)
const mockEmitFromServer = vi.mocked(emitFromServer)

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

describe('GET /api/export/pdf/[analysisId]', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('emits sc0red_cta_rendered_in_pdf after successful render when opportunities exist', async () => {
        mockBackendFetch.mockResolvedValue(baseAnalysis)

        const response = await GET(makeRequest(), { params: { analysisId: 'assess-1' } })

        expect(response.status).toBe(200)
        expect(mockEmitFromServer).toHaveBeenCalledTimes(1)
        expect(mockEmitFromServer).toHaveBeenCalledWith('sc0red_cta_rendered_in_pdf', {
            analysisId: 'assess-1',
            opportunityCount: 1,
        })
    })

    it('does not emit when there are no opportunities (CTA is not rendered)', async () => {
        mockBackendFetch.mockResolvedValue({ ...baseAnalysis, opportunities: [] })

        const response = await GET(makeRequest(), { params: { analysisId: 'assess-1' } })

        expect(response.status).toBe(200)
        expect(mockEmitFromServer).not.toHaveBeenCalled()
    })

    it('does not wait for emitFromServer before returning the PDF', async () => {
        mockBackendFetch.mockResolvedValue(baseAnalysis)
        // A never-resolving emit would block the response if the route
        // awaited it. We assert the response arrives anyway — proving the
        // emit is fire-and-forget (`void`) and cannot add latency.
        mockEmitFromServer.mockReturnValueOnce(new Promise(() => {}))

        const response = await GET(makeRequest(), { params: { analysisId: 'assess-1' } })

        expect(response.status).toBe(200)
        expect(mockEmitFromServer).toHaveBeenCalled()
    })

    it('returns the backend error status when the analysis fetch fails', async () => {
        mockBackendFetch.mockRejectedValue(new Error('upstream down'))

        const response = await GET(makeRequest(), { params: { analysisId: 'assess-1' } })

        expect(response.status).toBe(500)
        expect(mockEmitFromServer).not.toHaveBeenCalled()
    })
})
