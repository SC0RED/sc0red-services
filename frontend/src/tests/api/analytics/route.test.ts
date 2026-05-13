import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/serverToken', () => ({
    backendFetch: vi.fn(),
}))

import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'
import { POST } from '@/app/api/analytics/events/route'

const mockBackendFetch = vi.mocked(backendFetch)

function makeRequest(body: unknown): Request {
    return new Request('http://localhost/api/analytics/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    })
}

describe('POST /api/analytics/events', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('forwards the body to the backend and returns 202', async () => {
        mockBackendFetch.mockResolvedValue({ accepted: true })
        const payload = {
            event_id: 'uuid-1',
            event_type: 'sc0red_cta_rendered_strategy_map',
            timestamp: '2026-04-24T12:00:00.000Z',
            analytics_version: '1',
            source: 'web',
            analysis_id: 'assess-1',
            opportunity_count: 3,
            active_lever_filter: null,
        }

        const response = await POST(makeRequest(payload))

        expect(mockBackendFetch).toHaveBeenCalledWith('/api/analytics/events', {
            method: 'POST',
            body: payload,
        })
        expect(response.status).toBe(202)
        expect(await response.json()).toEqual({ accepted: true })
    })

    it('returns 401 when backendFetch throws Not authenticated', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('Not authenticated', 401))
        const response = await POST(makeRequest({}))
        expect(response.status).toBe(401)
        expect(await response.json()).toEqual({ error: 'Not authenticated' })
    })

    it('proxies a 400 validation error from the backend', async () => {
        mockBackendFetch.mockRejectedValue(new BackendError('Invalid event', 400))
        const response = await POST(makeRequest({ event_type: 'not_real' }))
        expect(response.status).toBe(400)
        expect(await response.json()).toEqual({ error: 'Invalid event' })
    })

    it('returns 500 on unexpected network error', async () => {
        mockBackendFetch.mockRejectedValue(new Error('Connection refused'))
        const response = await POST(makeRequest({}))
        expect(response.status).toBe(500)
        expect(await response.json()).toEqual({ error: 'Connection refused' })
    })
})
