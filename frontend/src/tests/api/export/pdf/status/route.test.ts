import { describe, it, expect, beforeEach, vi } from 'vitest'

vi.mock('@/lib/api/serverToken', () => ({
    backendFetch: vi.fn(),
}))

import { GET } from '@/app/api/export/pdf/[analysisId]/status/route'
import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'

const mockBackendFetch = vi.mocked(backendFetch)

function makeRequest(): Request {
    return new Request('http://localhost/api/export/pdf/assess-1/status')
}

beforeEach(() => {
    vi.clearAllMocks()
})

describe('GET /api/export/pdf/[analysisId]/status', () => {
    it('forwards status: none from the backend (no record yet)', async () => {
        mockBackendFetch.mockResolvedValue({ status: 'none' })

        const response = await GET(makeRequest(), { params: { analysisId: 'assess-1' } })

        expect(response.status).toBe(200)
        const body = (await response.json()) as { status: string }
        expect(body.status).toBe('none')
        expect(mockBackendFetch).toHaveBeenCalledWith('/api/export/pdf/assess-1/status')
    })

    it('forwards status: rendering with startedAt', async () => {
        mockBackendFetch.mockResolvedValue({
            status: 'rendering',
            startedAt: '2026-05-18T10:00:00Z',
        })

        const response = await GET(makeRequest(), { params: { analysisId: 'assess-1' } })

        expect(response.status).toBe(200)
        const body = (await response.json()) as { status: string; startedAt: string }
        expect(body.status).toBe('rendering')
        expect(body.startedAt).toBe('2026-05-18T10:00:00Z')
    })

    it('forwards status: ready with the presigned URL', async () => {
        mockBackendFetch.mockResolvedValue({
            status: 'ready',
            url: 'https://s3.example.com/pdf-exports/assess-1.pdf?sig=abc',
            generatedAt: '2026-05-18T10:00:13Z',
        })

        const response = await GET(makeRequest(), { params: { analysisId: 'assess-1' } })

        expect(response.status).toBe(200)
        const body = (await response.json()) as { status: string; url: string }
        expect(body.status).toBe('ready')
        expect(body.url).toContain('s3.example.com')
    })

    it('forwards status: failed with the synthetic stale-rendering message', async () => {
        // Backend folds rendering > 60 s into a synthetic failed without
        // mutating the persisted record — see Phase 1 spec.
        mockBackendFetch.mockResolvedValue({
            status: 'failed',
            error: 'Render appears stuck; try again.',
        })

        const response = await GET(makeRequest(), { params: { analysisId: 'assess-1' } })

        expect(response.status).toBe(200)
        const body = (await response.json()) as { status: string; error: string }
        expect(body.status).toBe('failed')
        expect(body.error).toContain('stuck')
    })

    it('propagates BackendError status (e.g., 404 not found)', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('Not found', 404))

        const response = await GET(makeRequest(), { params: { analysisId: 'missing' } })

        expect(response.status).toBe(404)
        const body = (await response.json()) as { error: string }
        expect(body.error).toBe('Not found')
    })

    it('returns 500 with the original error message on non-BackendError failures', async () => {
        mockBackendFetch.mockRejectedValue(new Error('upstream down'))

        const response = await GET(makeRequest(), { params: { analysisId: 'assess-1' } })

        expect(response.status).toBe(500)
        const body = (await response.json()) as { error: string }
        expect(body.error).toBe('upstream down')
    })
})
