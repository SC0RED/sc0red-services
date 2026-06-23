import { NextRequest } from 'next/server'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/serverToken', () => ({
    backendFetch: vi.fn(),
}))

import { POST } from '@/app/api/scan/[scanId]/source-url/route'
import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'

const mockBackendFetch = vi.mocked(backendFetch)

function makeRequest(body: unknown): NextRequest {
    return new NextRequest('http://localhost/api/scan/s-1/source-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    })
}

describe('POST /api/scan/[scanId]/source-url', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('forwards the sourceUrl body to the scoped backend route and relays the response', async () => {
        const backendResponse = { scanId: 's-1', status: 'discovering' }
        mockBackendFetch.mockResolvedValue(backendResponse)

        const response = await POST(makeRequest({ sourceUrl: 'https://firm.com/portfolio' }), {
            params: { scanId: 's-1' },
        })

        expect(mockBackendFetch).toHaveBeenCalledWith('/api/scan/s-1/source-url', {
            method: 'POST',
            body: { sourceUrl: 'https://firm.com/portfolio' },
        })
        expect(response.status).toBe(200)
        expect(await response.json()).toEqual(backendResponse)
    })

    it('proxies a 400 validation error from the backend', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('A valid http(s) sourceUrl is required', 400))
        const response = await POST(makeRequest({ sourceUrl: 'not-a-url' }), {
            params: { scanId: 's-1' },
        })
        expect(response.status).toBe(400)
        expect(await response.json()).toEqual({ error: 'A valid http(s) sourceUrl is required' })
    })

    it('returns 401 when backendFetch throws Not authenticated', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('Not authenticated', 401))
        const response = await POST(makeRequest({ sourceUrl: 'https://firm.com' }), {
            params: { scanId: 's-1' },
        })
        expect(response.status).toBe(401)
        expect(await response.json()).toEqual({ error: 'Not authenticated' })
    })

    it('returns 500 on unexpected network error', async () => {
        mockBackendFetch.mockRejectedValue(new Error('Connection refused'))
        const response = await POST(makeRequest({ sourceUrl: 'https://firm.com' }), {
            params: { scanId: 's-1' },
        })
        expect(response.status).toBe(500)
        expect(await response.json()).toEqual({ error: 'Connection refused' })
    })
})
