import { vi, describe, it, expect, beforeEach } from 'vitest'

vi.mock('@/lib/api/serverToken', () => ({
    backendFetch: vi.fn(),
}))

import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'
import { GET } from '@/app/api/config/route'

const mockBackendFetch = vi.mocked(backendFetch)

describe('GET /api/config', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('proxies to backend /api/config and returns data', async () => {
        const configData = {
            appsyncEndpoint: 'https://xxx.appsync-api.us-east-1.amazonaws.com/graphql',
            appsyncApiKey: 'da2-fakekey123',
        }
        mockBackendFetch.mockResolvedValue(configData)

        const response = await GET()

        expect(mockBackendFetch).toHaveBeenCalledWith('/api/config')
        expect(response.status).toBe(200)
        expect(await response.json()).toEqual(configData)
    })

    it('returns empty strings when backend returns empty config', async () => {
        const configData = { appsyncEndpoint: '', appsyncApiKey: '' }
        mockBackendFetch.mockResolvedValue(configData)

        const response = await GET()

        expect(response.status).toBe(200)
        expect(await response.json()).toEqual(configData)
    })

    it('returns 500 on fetch error', async () => {
        mockBackendFetch.mockRejectedValue(new Error('Connection refused'))

        const response = await GET()

        expect(response.status).toBe(500)
        expect(await response.json()).toEqual({ error: 'Connection refused' })
    })

    it('returns 401 when not authenticated', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('Not authenticated', 401))

        const response = await GET()

        expect(response.status).toBe(401)
        expect(await response.json()).toEqual({ error: 'Not authenticated' })
    })
})
