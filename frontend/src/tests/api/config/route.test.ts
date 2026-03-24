import { vi, describe, it, expect, beforeEach } from 'vitest'

const mockFetch = vi.fn()
global.fetch = mockFetch

vi.mock('@/lib/config', () => ({
    BACKEND_URL: 'http://localhost:8001',
}))

import { GET } from '@/app/api/config/route'

describe('GET /api/config', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('proxies to backend /api/config and returns data', async () => {
        const configData = {
            appsyncEndpoint: 'https://xxx.appsync-api.us-east-1.amazonaws.com/graphql',
            appsyncApiKey: 'da2-fakekey123',
        }
        mockFetch.mockResolvedValue({
            json: () => Promise.resolve(configData),
        })

        const response = await GET()

        expect(mockFetch).toHaveBeenCalledWith('http://localhost:8001/api/config')
        expect(response.status).toBe(200)
        expect(await response.json()).toEqual(configData)
    })

    it('returns empty strings when backend returns empty config', async () => {
        const configData = { appsyncEndpoint: '', appsyncApiKey: '' }
        mockFetch.mockResolvedValue({
            json: () => Promise.resolve(configData),
        })

        const response = await GET()

        expect(response.status).toBe(200)
        expect(await response.json()).toEqual(configData)
    })

    it('returns 500 on fetch error', async () => {
        mockFetch.mockRejectedValue(new Error('Connection refused'))

        const response = await GET()

        expect(response.status).toBe(500)
        expect(await response.json()).toEqual({ error: 'Connection refused' })
    })
})
