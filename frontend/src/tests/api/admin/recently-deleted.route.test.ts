import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/serverToken', () => ({
    backendFetch: vi.fn(),
}))

import { GET } from '@/app/api/admin/recently-deleted/route'
import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'

const mockBackendFetch = vi.mocked(backendFetch)

function makeRequest(window?: string): { nextUrl: URL } {
    // The route uses `request.nextUrl.searchParams` from NextRequest.
    // The signature is loose enough that we can pass a minimal stand-in
    // — only `nextUrl.searchParams.get(...)` is read.
    const url = window
        ? `http://localhost/api/admin/recently-deleted?window=${encodeURIComponent(window)}`
        : 'http://localhost/api/admin/recently-deleted'
    return { nextUrl: new URL(url) }
}

describe('GET /api/admin/recently-deleted', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('forwards to the backend with no window when none provided', async () => {
        const records = [
            {
                id: 'c-1',
                type: 'analysis',
                displayName: 'Acme Corp',
                scanId: null,
                deletedAt: '2026-04-25T12:00:00Z',
                deletedBy: { id: 'user-1', name: 'Alice' },
                parentTombstoned: false,
            },
        ]
        mockBackendFetch.mockResolvedValue({ records })

        const response = await GET(makeRequest() as never)

        expect(mockBackendFetch).toHaveBeenCalledWith('/api/admin/recently-deleted')
        expect(response.status).toBe(200)
        expect(await response.json()).toEqual({ records })
    })

    it('forwards the window query param to the backend', async () => {
        mockBackendFetch.mockResolvedValue({ records: [] })

        await GET(makeRequest('7d') as never)

        expect(mockBackendFetch).toHaveBeenCalledWith('/api/admin/recently-deleted?window=7d')
    })

    it('relays a 401 from the backend (unauthenticated)', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('Not authenticated', 401))
        const response = await GET(makeRequest() as never)
        expect(response.status).toBe(401)
        expect(await response.json()).toEqual({ error: 'Not authenticated' })
    })

    it('relays a 403 from the backend (analyst role)', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('Admin role required', 403))
        const response = await GET(makeRequest() as never)
        expect(response.status).toBe(403)
        expect(await response.json()).toEqual({ error: 'Admin role required' })
    })

    it('returns 500 on unexpected network error', async () => {
        mockBackendFetch.mockRejectedValue(new Error('Connection refused'))
        const response = await GET(makeRequest() as never)
        expect(response.status).toBe(500)
        expect(await response.json()).toEqual({ error: 'Connection refused' })
    })
})
