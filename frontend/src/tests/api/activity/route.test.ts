import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/serverToken', () => ({
    backendFetch: vi.fn(),
}))

import { GET } from '@/app/api/activity/route'
import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'

const mockBackendFetch = vi.mocked(backendFetch)

describe('GET /api/activity', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('forwards to the backend and returns the events payload unchanged', async () => {
        const events = [
            {
                id: 'scan_started:scan-1',
                type: 'scan_started',
                actor: { id: 'user-1', name: 'Alice' },
                target: { id: 'scan-1', name: 'acme.com', type: 'scan' },
                timestamp: '2026-04-26T12:00:00Z',
                summary: 'Alice started a portfolio scan',
            },
        ]
        mockBackendFetch.mockResolvedValue({ events })

        const response = await GET()

        expect(mockBackendFetch).toHaveBeenCalledWith('/api/activity')
        expect(response.status).toBe(200)
        expect(await response.json()).toEqual({ events })
    })

    it('returns 401 when backendFetch throws Not authenticated', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('Not authenticated', 401))
        const response = await GET()
        expect(response.status).toBe(401)
        expect(await response.json()).toEqual({ error: 'Not authenticated' })
    })

    it('returns 500 on unexpected network error', async () => {
        mockBackendFetch.mockRejectedValue(new Error('Connection refused'))
        const response = await GET()
        expect(response.status).toBe(500)
        expect(await response.json()).toEqual({ error: 'Connection refused' })
    })
})
