import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { emit } from '@/lib/analytics/emitEvent'

describe('emit (browser)', () => {
    const originalFetch = globalThis.fetch

    beforeEach(() => {
        vi.useFakeTimers()
        vi.setSystemTime(new Date('2026-04-24T12:00:00.000Z'))
    })

    afterEach(() => {
        globalThis.fetch = originalFetch
        vi.unstubAllEnvs()
        vi.useRealTimers()
        vi.restoreAllMocks()
    })

    it('POSTs to /api/analytics/events with the correct envelope', async () => {
        const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 202 }))
        globalThis.fetch = fetchMock as typeof fetch

        await emit('sc0red_cta_banner_expanded', {
            analysisId: 'assess-1',
            opportunityCount: 3,
            activeLeverFilter: 'Revenue Side',
        })

        expect(fetchMock).toHaveBeenCalledTimes(1)
        const [url, init] = fetchMock.mock.calls[0]
        expect(url).toBe('/api/analytics/events')
        expect(init).toMatchObject({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            keepalive: true,
        })
        const body = JSON.parse(init.body as string)
        expect(body).toMatchObject({
            event_type: 'sc0red_cta_banner_expanded',
            source: 'web',
            analytics_version: '1',
            analysis_id: 'assess-1',
            opportunity_count: 3,
            active_lever_filter: 'Revenue Side',
            timestamp: '2026-04-24T12:00:00.000Z',
        })
        expect(body.event_id).toBeTruthy()
        expect(typeof body.event_id).toBe('string')
    })

    it('accepts a null active_lever_filter', async () => {
        const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 202 }))
        globalThis.fetch = fetchMock as typeof fetch

        await emit('sc0red_cta_clicked', {
            analysisId: 'assess-1',
            opportunityCount: 0,
            activeLeverFilter: null,
        })

        const body = JSON.parse(fetchMock.mock.calls[0][1].body as string)
        expect(body.active_lever_filter).toBeNull()
        expect(body.event_type).toBe('sc0red_cta_clicked')
    })

    it('does not throw when the network request fails', async () => {
        globalThis.fetch = vi.fn().mockRejectedValue(new Error('offline')) as typeof fetch
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
        vi.stubEnv('NODE_ENV', 'development')

        await expect(
            emit('sc0red_cta_banner_expanded', {
                analysisId: 'assess-1',
                opportunityCount: 1,
                activeLeverFilter: null,
            })
        ).resolves.toBeUndefined()

        expect(warnSpy).toHaveBeenCalled()
    })

    it('does not throw when the server returns a non-2xx', async () => {
        globalThis.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 500 })) as typeof fetch
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
        vi.stubEnv('NODE_ENV', 'development')

        await expect(
            emit('sc0red_cta_banner_expanded', {
                analysisId: 'assess-1',
                opportunityCount: 1,
                activeLeverFilter: null,
            })
        ).resolves.toBeUndefined()

        expect(warnSpy).toHaveBeenCalled()
    })

    it('silences warnings in production', async () => {
        globalThis.fetch = vi.fn().mockRejectedValue(new Error('x')) as typeof fetch
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
        vi.stubEnv('NODE_ENV', 'production')

        await emit('sc0red_cta_banner_expanded', {
            analysisId: 'assess-1',
            opportunityCount: 1,
            activeLeverFilter: null,
        })

        expect(warnSpy).not.toHaveBeenCalled()
    })
})
