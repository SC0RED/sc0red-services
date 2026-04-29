import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/serverToken', () => ({
    backendFetch: vi.fn(),
}))

import { POST } from '@/app/api/admin/restore/route'
import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'

const mockBackendFetch = vi.mocked(backendFetch)

function makeRequest(body: unknown): Request {
    return new Request('http://localhost/api/admin/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    })
}

describe('POST /api/admin/restore', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('forwards the body to the backend and relays the response', async () => {
        const backendResponse = {
            restored: ['c-1', 'scan-2'],
            failed: [],
        }
        mockBackendFetch.mockResolvedValue(backendResponse)

        const response = await POST(makeRequest({ ids: ['c-1', 'scan-2'] }))

        expect(mockBackendFetch).toHaveBeenCalledWith('/api/admin/restore', {
            method: 'POST',
            body: { ids: ['c-1', 'scan-2'] },
        })
        expect(response.status).toBe(200)
        expect(await response.json()).toEqual(backendResponse)
    })

    it('proxies partial failures (ttl_expired / not_found) unchanged', async () => {
        const backendResponse = {
            restored: ['c-1'],
            failed: [
                { id: 'c-2', reason: 'ttl_expired' },
                { id: 'c-3', reason: 'not_found' },
            ],
        }
        mockBackendFetch.mockResolvedValue(backendResponse)

        const response = await POST(makeRequest({ ids: ['c-1', 'c-2', 'c-3'] }))

        expect(response.status).toBe(200)
        expect(await response.json()).toEqual(backendResponse)
    })

    it('relays a 400 from the backend (invalid body)', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('`ids` must not be empty', 400))
        const response = await POST(makeRequest({ ids: [] }))
        expect(response.status).toBe(400)
        expect(await response.json()).toEqual({ error: '`ids` must not be empty' })
    })

    it('relays a 401 from the backend (unauthenticated)', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('Not authenticated', 401))
        const response = await POST(makeRequest({ ids: ['c-1'] }))
        expect(response.status).toBe(401)
        expect(await response.json()).toEqual({ error: 'Not authenticated' })
    })

    it('relays a 403 from the backend (analyst role)', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('Admin role required', 403))
        const response = await POST(makeRequest({ ids: ['c-1'] }))
        expect(response.status).toBe(403)
        expect(await response.json()).toEqual({ error: 'Admin role required' })
    })

    it('returns 500 on unexpected network error', async () => {
        mockBackendFetch.mockRejectedValue(new Error('Connection refused'))
        const response = await POST(makeRequest({ ids: ['c-1'] }))
        expect(response.status).toBe(500)
        expect(await response.json()).toEqual({ error: 'Connection refused' })
    })
})
