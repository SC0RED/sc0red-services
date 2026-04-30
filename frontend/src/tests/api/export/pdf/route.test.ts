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

import { GET } from '@/app/api/export/pdf/[analysisId]/route'
import { emitFromServer } from '@/lib/analytics/emitEvent.server'
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
