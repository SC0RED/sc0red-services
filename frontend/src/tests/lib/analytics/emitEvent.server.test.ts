import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/serverToken', () => ({
    backendFetch: vi.fn(),
}))

import { emitFromServer } from '@/lib/analytics/emitEvent.server'
import { backendFetch } from '@/lib/api/serverToken'

const mockBackendFetch = vi.mocked(backendFetch)

describe('emitFromServer (server-side)', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        vi.useFakeTimers()
        vi.setSystemTime(new Date('2026-04-24T12:00:00.000Z'))
    })

    afterEach(() => {
        vi.unstubAllEnvs()
        vi.useRealTimers()
    })

    it('calls backendFetch with the PDF event envelope', async () => {
        mockBackendFetch.mockResolvedValue({ accepted: true })

        await emitFromServer('sc0red_cta_rendered_in_pdf', {
            analysisId: 'assess-1',
            opportunityCount: 5,
        })

        expect(mockBackendFetch).toHaveBeenCalledTimes(1)
        const [path, options] = mockBackendFetch.mock.calls[0]
        expect(path).toBe('/api/analytics/events')
        expect(options).toMatchObject({ method: 'POST' })
        const body = options?.body as Record<string, unknown>
        expect(body).toMatchObject({
            event_type: 'sc0red_cta_rendered_in_pdf',
            source: 'pdf',
            analytics_version: '1',
            analysis_id: 'assess-1',
            opportunity_count: 5,
            active_lever_filter: null,
            timestamp: '2026-04-24T12:00:00.000Z',
        })
        expect(body.event_id).toBeTruthy()
    })

    it('does not throw when backendFetch rejects', async () => {
        mockBackendFetch.mockRejectedValue(new Error('backend unreachable'))
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

        await expect(
            emitFromServer('sc0red_cta_rendered_in_pdf', {
                analysisId: 'assess-1',
                opportunityCount: 1,
            })
        ).resolves.toBeUndefined()

        expect(warnSpy).toHaveBeenCalled()
    })
})
