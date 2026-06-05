import { vi, describe, it, expect, beforeEach } from 'vitest'

vi.mock('@/lib/api/serverToken', () => ({
    backendFetch: vi.fn(),
}))

import { backendFetch } from '@/lib/api/serverToken'
import { POST } from '@/app/api/oauth/approve/route'

const mockBackendFetch = vi.mocked(backendFetch)

function makeRequest(body: unknown) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return { json: async () => body } as any
}

describe('POST /api/oauth/approve', () => {
    beforeEach(() => vi.clearAllMocks())

    it('forwards the consent body to the backend as an OBJECT (not double-encoded)', async () => {
        // Regression guard for the double-encoding bug: backendFetch stringifies
        // the body itself, so the route must pass the parsed object. Passing
        // JSON.stringify(body) here made the backend receive a string →
        // AttributeError 'str' object has no attribute 'get' → 502.
        const consent = {
            client_id: 'c1',
            redirect_uri: 'http://localhost:6274/oauth/callback',
            code_challenge: 'abc',
            scope: 'read write',
            state: 's1',
        }
        mockBackendFetch.mockResolvedValue({ redirect_url: 'http://localhost:6274/oauth/callback?code=xyz' })

        const response = await POST(makeRequest(consent))

        expect(mockBackendFetch).toHaveBeenCalledWith('/api/oauth/approve', {
            method: 'POST',
            body: consent,
        })
        // The body forwarded must be the object itself, never a JSON string.
        expect(typeof mockBackendFetch.mock.calls[0][1]?.body).toBe('object')
        expect(response.status).toBe(200)
        expect(await response.json()).toEqual({
            redirect_url: 'http://localhost:6274/oauth/callback?code=xyz',
        })
    })

    it('returns 500 with the backend error message on failure', async () => {
        mockBackendFetch.mockRejectedValue(new Error('Unknown client_id'))
        const response = await POST(makeRequest({ client_id: 'bad' }))
        expect(response.status).toBe(500)
        expect(await response.json()).toEqual({ error: 'Unknown client_id' })
    })
})
