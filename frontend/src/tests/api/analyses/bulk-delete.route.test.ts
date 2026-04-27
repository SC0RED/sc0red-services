import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/serverToken', () => ({
    backendFetch: vi.fn(),
}))

import { POST } from '@/app/api/analyses/bulk-delete/route'
import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'

const mockBackendFetch = vi.mocked(backendFetch)

function makeRequest(body: unknown): Request {
    return new Request('http://localhost/api/analyses/bulk-delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    })
}

describe('POST /api/analyses/bulk-delete', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('forwards the body to the backend and relays the response', async () => {
        const backendResponse = {
            deleted: ['a-1', 'a-2'],
            failed: [],
            deletedScans: ['scan-1'],
        }
        mockBackendFetch.mockResolvedValue(backendResponse)

        const response = await POST(makeRequest({ ids: ['a-1', 'a-2'] }))

        expect(mockBackendFetch).toHaveBeenCalledWith('/api/analyses/bulk-delete', {
            method: 'POST',
            body: { ids: ['a-1', 'a-2'] },
        })
        expect(response.status).toBe(200)
        expect(await response.json()).toEqual(backendResponse)
    })

    it('proxies a partial-failure response unchanged', async () => {
        const backendResponse = {
            deleted: ['a-2'],
            failed: [{ id: 'a-1', reason: 'not_found' }],
            deletedScans: [],
        }
        mockBackendFetch.mockResolvedValue(backendResponse)

        const response = await POST(makeRequest({ ids: ['a-1', 'a-2'] }))

        expect(response.status).toBe(200)
        expect(await response.json()).toEqual(backendResponse)
    })

    it('returns 401 when backendFetch throws Not authenticated', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('Not authenticated', 401))
        const response = await POST(makeRequest({ ids: ['a-1'] }))
        expect(response.status).toBe(401)
        expect(await response.json()).toEqual({ error: 'Not authenticated' })
    })

    it('proxies a 400 validation error from the backend', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('Body must include `ids: string[]`', 400))
        const response = await POST(makeRequest({}))
        expect(response.status).toBe(400)
        expect(await response.json()).toEqual({ error: 'Body must include `ids: string[]`' })
    })

    it('returns 500 on unexpected network error', async () => {
        mockBackendFetch.mockRejectedValue(new Error('Connection refused'))
        const response = await POST(makeRequest({ ids: ['a-1'] }))
        expect(response.status).toBe(500)
        expect(await response.json()).toEqual({ error: 'Connection refused' })
    })
})
