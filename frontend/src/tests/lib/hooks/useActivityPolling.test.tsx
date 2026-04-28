import { renderHook, act } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useActivityPolling } from '@/lib/hooks/useActivityPolling'
import type { ActivityEvent } from '@/lib/types/api'

const SAMPLE_EVENT: ActivityEvent = {
    id: 'scan_started:scan-1',
    type: 'scan_started',
    actor: { id: 'user-1', name: 'Alice' },
    target: { id: 'scan-1', name: 'acme.com', type: 'scan' },
    timestamp: '2026-04-26T12:00:00Z',
    summary: 'Alice started a portfolio scan',
}

function fetchOk(events: ActivityEvent[]): Response {
    return {
        ok: true,
        status: 200,
        json: async () => ({ events }),
    } as Response
}

/**
 * Flush microtasks AND any pending timers up to `ms`. The hook's poll
 * resolves an async fetch within an effect — microtask flushing is what
 * actually advances the test, not the timer.
 */
async function flush(ms = 0): Promise<void> {
    await act(async () => {
        await vi.advanceTimersByTimeAsync(ms)
    })
}

describe('useActivityPolling', () => {
    const ORIGINAL_FETCH = global.fetch

    beforeEach(() => {
        vi.useFakeTimers()
    })

    afterEach(() => {
        global.fetch = ORIGINAL_FETCH
        vi.useRealTimers()
    })

    it('fetches once on mount and exposes events', async () => {
        const fetchMock = vi.fn().mockResolvedValue(fetchOk([SAMPLE_EVENT]))
        global.fetch = fetchMock as unknown as typeof fetch

        const { result } = renderHook(() => useActivityPolling())
        await flush()

        expect(result.current.loading).toBe(false)
        expect(result.current.events).toEqual([SAMPLE_EVENT])
        expect(fetchMock).toHaveBeenCalledWith('/api/activity', { credentials: 'include' })
    })

    it('re-polls every 30 seconds', async () => {
        const fetchMock = vi.fn().mockResolvedValue(fetchOk([]))
        global.fetch = fetchMock as unknown as typeof fetch

        renderHook(() => useActivityPolling())
        await flush()
        expect(fetchMock).toHaveBeenCalledTimes(1)

        await flush(30_000)
        expect(fetchMock).toHaveBeenCalledTimes(2)

        await flush(30_000)
        expect(fetchMock).toHaveBeenCalledTimes(3)
    })

    it('stops polling when the component unmounts', async () => {
        const fetchMock = vi.fn().mockResolvedValue(fetchOk([]))
        global.fetch = fetchMock as unknown as typeof fetch

        const { unmount } = renderHook(() => useActivityPolling())
        await flush()
        expect(fetchMock).toHaveBeenCalledTimes(1)

        unmount()

        await flush(60_000)
        expect(fetchMock).toHaveBeenCalledTimes(1)
    })

    it('absorbs network errors silently and surfaces them via `error`', async () => {
        const fetchMock = vi.fn().mockRejectedValue(new Error('network down'))
        global.fetch = fetchMock as unknown as typeof fetch

        const { result } = renderHook(() => useActivityPolling())
        await flush()

        expect(result.current.loading).toBe(false)
        expect(result.current.error).toBeInstanceOf(Error)
        expect(result.current.error?.message).toBe('network down')
        expect(result.current.events).toEqual([])
    })

    it('clears the error on a subsequent successful poll', async () => {
        const fetchMock = vi
            .fn()
            .mockRejectedValueOnce(new Error('flake'))
            .mockResolvedValue(fetchOk([SAMPLE_EVENT]))
        global.fetch = fetchMock as unknown as typeof fetch

        const { result } = renderHook(() => useActivityPolling())
        await flush()
        expect(result.current.error).not.toBeNull()

        await flush(30_000)
        expect(result.current.error).toBeNull()
        expect(result.current.events).toEqual([SAMPLE_EVENT])
    })

    it('rejects out-of-order results from a slower in-flight request', async () => {
        // Race-safety regression guard: an earlier request that resolves
        // AFTER a later one must NOT overwrite the newer result.
        const SLOW_EVENT: ActivityEvent = { ...SAMPLE_EVENT, id: 'slow' }
        const FAST_EVENT: ActivityEvent = { ...SAMPLE_EVENT, id: 'fast' }

        let resolveSlow: (value: Response) => void = () => {}
        const slowPromise = new Promise<Response>((resolve) => {
            resolveSlow = resolve
        })

        const fetchMock = vi
            .fn()
            // First call is the slow one — held until we resolveSlow().
            .mockReturnValueOnce(slowPromise)
            // Second call resolves immediately.
            .mockResolvedValue(fetchOk([FAST_EVENT]))
        global.fetch = fetchMock as unknown as typeof fetch

        const { result } = renderHook(() => useActivityPolling())
        // Mount fires the slow request; advance to fire the second poll.
        await flush(30_000)

        // Fast request resolves first → state has FAST_EVENT.
        expect(result.current.events).toEqual([FAST_EVENT])

        // Now resolve the slow request — its older generation marker
        // should cause the result to be discarded.
        await act(async () => {
            resolveSlow(fetchOk([SLOW_EVENT]))
            await vi.advanceTimersByTimeAsync(0)
        })

        expect(result.current.events).toEqual([FAST_EVENT])
    })
})
