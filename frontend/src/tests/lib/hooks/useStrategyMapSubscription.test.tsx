import { renderHook, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

vi.mock('@/lib/appsync/client', () => ({
    createAppSyncSubscription: vi.fn(),
}))

import { createAppSyncSubscription } from '@/lib/appsync/client'
import { useStrategyMapSubscription } from '@/lib/hooks/useStrategyMapSubscription'

const mockCreateSubscription = vi.mocked(createAppSyncSubscription)

/**
 * AppSync subscription hook used by the on-demand strategy-map flow
 * (per the `strategy-map-on-demand` spec). Mirrors the test layout of
 * `useScanRealtime.test.tsx` since both subscribe to the same
 * `onScanProgress` channel — the strategy-map hook adds:
 *   1. Client-side filtering by `companyId === analysisId` AND status
 *      prefix `strategy_map_*`.
 *   2. A 90-second client-side fallback timer that fires `onTimeout` when
 *      no event arrives.
 */
describe('useStrategyMapSubscription', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        vi.useFakeTimers()
        global.fetch = vi.fn()
    })

    afterEach(() => {
        vi.useRealTimers()
        vi.restoreAllMocks()
    })

    function makeOptions() {
        return {
            analysisId: 'a-1',
            scanId: 's-1',
            onComplete: vi.fn(),
            onFailed: vi.fn(),
            onTimeout: vi.fn(),
        }
    }

    function configureAppSync() {
        const fetchMock = vi.fn().mockResolvedValue({
            json: () =>
                Promise.resolve({
                    appsyncEndpoint: 'https://xxx.appsync-api.us-east-1.amazonaws.com/graphql',
                    appsyncApiKey: 'da2-fakekey',
                }),
        })
        global.fetch = fetchMock
        return fetchMock
    }

    it('does not subscribe when AppSync is not configured', async () => {
        const fetchMock = vi.fn().mockResolvedValue({
            json: () => Promise.resolve({ appsyncEndpoint: '', appsyncApiKey: '' }),
        })
        global.fetch = fetchMock

        const { result } = renderHook(() => useStrategyMapSubscription())

        await act(async () => {
            await result.current.start(makeOptions())
        })

        expect(fetchMock).toHaveBeenCalledWith('/api/config')
        expect(mockCreateSubscription).not.toHaveBeenCalled()
    })

    it('creates subscription with the scanId variable when configured', async () => {
        configureAppSync()
        mockCreateSubscription.mockReturnValue(vi.fn())

        const { result } = renderHook(() => useStrategyMapSubscription())

        await act(async () => {
            await result.current.start(makeOptions())
        })

        expect(mockCreateSubscription).toHaveBeenCalledTimes(1)
        const callArgs = mockCreateSubscription.mock.calls[0]
        expect(callArgs[0]).toEqual({
            endpoint: 'https://xxx.appsync-api.us-east-1.amazonaws.com/graphql',
            apiKey: 'da2-fakekey',
        })
        expect(callArgs[2]).toEqual({ scanId: 's-1' })
    })

    it('routes strategy_map_complete events to onComplete and stops the subscription', async () => {
        configureAppSync()
        let capturedOnData: ((data: Record<string, unknown>) => void) | null = null
        const unsubscribe = vi.fn()
        mockCreateSubscription.mockImplementation((_config, _query, _vars, handlers) => {
            capturedOnData = handlers.onData
            return unsubscribe
        })

        const options = makeOptions()
        const { result } = renderHook(() => useStrategyMapSubscription())
        await act(async () => {
            await result.current.start(options)
        })

        act(() => {
            capturedOnData!({
                onScanProgress: {
                    scanId: 's-1',
                    companyId: 'a-1',
                    progress: 100,
                    progressLabel: 'Strategy map complete',
                    status: 'strategy_map_complete',
                },
            })
        })

        expect(options.onComplete).toHaveBeenCalledTimes(1)
        expect(options.onFailed).not.toHaveBeenCalled()
        // Subscription torn down + timer cleared after the terminal event.
        expect(unsubscribe).toHaveBeenCalledTimes(1)
    })

    it('routes strategy_map_failed events to onFailed', async () => {
        configureAppSync()
        let capturedOnData: ((data: Record<string, unknown>) => void) | null = null
        mockCreateSubscription.mockImplementation((_config, _query, _vars, handlers) => {
            capturedOnData = handlers.onData
            return vi.fn()
        })

        const options = makeOptions()
        const { result } = renderHook(() => useStrategyMapSubscription())
        await act(async () => {
            await result.current.start(options)
        })

        act(() => {
            capturedOnData!({
                onScanProgress: {
                    scanId: 's-1',
                    companyId: 'a-1',
                    progress: 0,
                    progressLabel: 'Strategy map failed',
                    status: 'strategy_map_failed',
                },
            })
        })

        expect(options.onFailed).toHaveBeenCalledTimes(1)
        expect(options.onComplete).not.toHaveBeenCalled()
    })

    it('ignores events for a different analysisId on the same scan', async () => {
        // The worker shares the `onScanProgress` channel filtered by
        // scanId. If two analyses share a scan (re-analyse case) the
        // hook must filter by companyId so the OTHER analysis's events
        // don't trigger our callbacks.
        configureAppSync()
        let capturedOnData: ((data: Record<string, unknown>) => void) | null = null
        mockCreateSubscription.mockImplementation((_config, _query, _vars, handlers) => {
            capturedOnData = handlers.onData
            return vi.fn()
        })

        const options = makeOptions()
        const { result } = renderHook(() => useStrategyMapSubscription())
        await act(async () => {
            await result.current.start(options)
        })

        act(() => {
            capturedOnData!({
                onScanProgress: {
                    scanId: 's-1',
                    companyId: 'a-OTHER',
                    progress: 100,
                    progressLabel: 'Strategy map complete',
                    status: 'strategy_map_complete',
                },
            })
        })

        expect(options.onComplete).not.toHaveBeenCalled()
        expect(options.onFailed).not.toHaveBeenCalled()
    })

    it('ignores non-strategy-map statuses on the same channel', async () => {
        // The base scan pipeline also pushes events on this channel
        // (status `running`, `complete`). They must NOT trigger the
        // strategy-map callbacks.
        configureAppSync()
        let capturedOnData: ((data: Record<string, unknown>) => void) | null = null
        mockCreateSubscription.mockImplementation((_config, _query, _vars, handlers) => {
            capturedOnData = handlers.onData
            return vi.fn()
        })

        const options = makeOptions()
        const { result } = renderHook(() => useStrategyMapSubscription())
        await act(async () => {
            await result.current.start(options)
        })

        act(() => {
            capturedOnData!({
                onScanProgress: {
                    scanId: 's-1',
                    companyId: 'a-1',
                    progress: 50,
                    progressLabel: 'Running',
                    status: 'running',
                },
            })
            capturedOnData!({
                onScanProgress: {
                    scanId: 's-1',
                    companyId: 'a-1',
                    progress: 100,
                    progressLabel: 'Complete',
                    status: 'complete',
                },
            })
        })

        expect(options.onComplete).not.toHaveBeenCalled()
        expect(options.onFailed).not.toHaveBeenCalled()
    })

    it('fires onTimeout once after the fallback window if no event arrives', async () => {
        configureAppSync()
        const unsubscribe = vi.fn()
        mockCreateSubscription.mockReturnValue(unsubscribe)

        const options = makeOptions()
        const { result } = renderHook(() => useStrategyMapSubscription())
        await act(async () => {
            await result.current.start({ ...options, timeoutMs: 1000 })
        })

        // Advance past the fallback window.
        act(() => {
            vi.advanceTimersByTime(1000)
        })

        expect(options.onTimeout).toHaveBeenCalledTimes(1)
        // Subscription torn down at timeout to prevent late events from
        // calling stale callbacks.
        expect(unsubscribe).toHaveBeenCalledTimes(1)
    })

    it('cancels the fallback timer when a terminal event arrives', async () => {
        configureAppSync()
        let capturedOnData: ((data: Record<string, unknown>) => void) | null = null
        mockCreateSubscription.mockImplementation((_config, _query, _vars, handlers) => {
            capturedOnData = handlers.onData
            return vi.fn()
        })

        const options = makeOptions()
        const { result } = renderHook(() => useStrategyMapSubscription())
        await act(async () => {
            await result.current.start({ ...options, timeoutMs: 1000 })
        })

        // Terminal event fires before the timeout window elapses.
        act(() => {
            capturedOnData!({
                onScanProgress: {
                    scanId: 's-1',
                    companyId: 'a-1',
                    progress: 100,
                    progressLabel: 'Complete',
                    status: 'strategy_map_complete',
                },
            })
        })

        // Advance past the original window — onTimeout must NOT fire
        // (the timer was cleared by the terminal event).
        act(() => {
            vi.advanceTimersByTime(1000)
        })

        expect(options.onComplete).toHaveBeenCalledTimes(1)
        expect(options.onTimeout).not.toHaveBeenCalled()
    })

    it('cleans up subscription + timer on stop()', async () => {
        configureAppSync()
        const unsubscribe = vi.fn()
        mockCreateSubscription.mockReturnValue(unsubscribe)

        const options = makeOptions()
        const { result } = renderHook(() => useStrategyMapSubscription())
        await act(async () => {
            await result.current.start({ ...options, timeoutMs: 1000 })
        })

        act(() => {
            result.current.stop()
        })

        expect(unsubscribe).toHaveBeenCalledTimes(1)

        // Advance past the original window — onTimeout must NOT fire
        // because stop() cleared it.
        act(() => {
            vi.advanceTimersByTime(1000)
        })
        expect(options.onTimeout).not.toHaveBeenCalled()
    })

    it('cleans up on unmount', async () => {
        configureAppSync()
        const unsubscribe = vi.fn()
        mockCreateSubscription.mockReturnValue(unsubscribe)

        const { result, unmount } = renderHook(() => useStrategyMapSubscription())

        await act(async () => {
            await result.current.start(makeOptions())
        })

        unmount()

        expect(unsubscribe).toHaveBeenCalled()
    })

    it('start() called twice tears down the prior subscription before creating a new one', async () => {
        // Defends against a re-render that fires the effect twice — the
        // hook must NOT leak a second subscription on top of the first.
        configureAppSync()
        const unsubscribe1 = vi.fn()
        const unsubscribe2 = vi.fn()
        mockCreateSubscription.mockReturnValueOnce(unsubscribe1).mockReturnValueOnce(unsubscribe2)

        const { result } = renderHook(() => useStrategyMapSubscription())

        await act(async () => {
            await result.current.start(makeOptions())
        })
        await act(async () => {
            await result.current.start(makeOptions())
        })

        expect(unsubscribe1).toHaveBeenCalledTimes(1)
        expect(mockCreateSubscription).toHaveBeenCalledTimes(2)
    })

    it('silently handles config fetch failure', async () => {
        global.fetch = vi.fn().mockRejectedValue(new Error('Network error'))

        const { result } = renderHook(() => useStrategyMapSubscription())

        let started: boolean | undefined
        await act(async () => {
            started = await result.current.start(makeOptions())
        })

        expect(started).toBe(false)
        expect(mockCreateSubscription).not.toHaveBeenCalled()
    })
})
