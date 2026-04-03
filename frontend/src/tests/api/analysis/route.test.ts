import { vi, describe, it, expect, beforeEach } from 'vitest'

vi.mock('@/lib/api/serverToken', () => ({
    backendFetch: vi.fn(),
}))

import { NextRequest } from 'next/server'

import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'
import { GET, DELETE } from '@/app/api/analysis/[analysisId]/route'

const mockBackendFetch = vi.mocked(backendFetch)
const mockReq = {} as NextRequest

describe('GET /api/analysis/[analysisId]', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('returns 200 with the analysis data on success', async () => {
        const mockData = { id: 'test-id', companyName: 'Acme Corp', overallRiskScore: 7.2 }
        mockBackendFetch.mockResolvedValue(mockData)

        const res = await GET(mockReq, { params: { analysisId: 'test-id' } })

        expect(res.status).toBe(200)
        expect(await res.json()).toEqual(mockData)
        expect(mockBackendFetch).toHaveBeenCalledWith('/api/analysis/test-id')
    })

    it('returns 404 when BackendError with status 404 is thrown', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('Not found', 404))

        const res = await GET(mockReq, { params: { analysisId: 'bad-id' } })

        expect(res.status).toBe(404)
        expect(await res.json()).toEqual({ error: 'Not found' })
    })

    it('returns 401 when BackendError with status 401 is thrown', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('Not authenticated', 401))

        const res = await GET(mockReq, { params: { analysisId: 'test-id' } })

        expect(res.status).toBe(401)
        expect(await res.json()).toEqual({ error: 'Not authenticated' })
    })

    it('returns 500 for unexpected errors', async () => {
        mockBackendFetch.mockRejectedValue(new Error('Connection refused'))

        const res = await GET(mockReq, { params: { analysisId: 'test-id' } })

        expect(res.status).toBe(500)
        expect(await res.json()).toEqual({ error: 'Connection refused' })
    })
})

describe('DELETE /api/analysis/[analysisId]', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('returns 200 on successful delete', async () => {
        mockBackendFetch.mockResolvedValue({ deleted: true })

        const res = await DELETE(mockReq, { params: { analysisId: 'test-id' } })

        expect(res.status).toBe(200)
        expect(mockBackendFetch).toHaveBeenCalledWith('/api/analysis/test-id', { method: 'DELETE' })
    })

    it('returns 401 when BackendError with status 401 is thrown', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('Not authenticated', 401))

        const res = await DELETE(mockReq, { params: { analysisId: 'test-id' } })

        expect(res.status).toBe(401)
    })

    it('returns 404 when the analysis does not exist', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('Not found', 404))

        const res = await DELETE(mockReq, { params: { analysisId: 'missing-id' } })

        expect(res.status).toBe(404)
    })

    it('returns 500 for unexpected errors', async () => {
        mockBackendFetch.mockRejectedValue(new Error('DB timeout'))

        const res = await DELETE(mockReq, { params: { analysisId: 'test-id' } })

        expect(res.status).toBe(500)
        expect(await res.json()).toEqual({ error: 'DB timeout' })
    })
})
