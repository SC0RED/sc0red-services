import { renderHook, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

import { useScanPolling } from '@/lib/hooks/useScanPolling'

describe('useScanPolling', () => {
    let pollCallback: (() => Promise<void>) | null
    const realSetInterval = globalThis.setInterval.bind(globalThis)

    beforeEach(() => {
        pollCallback = null
        vi.spyOn(global, 'setInterval').mockImplementation((callback: () => void, delay?: number) => {
            if (delay === 3000) {
                pollCallback = callback as () => Promise<void>
                return 999 as unknown as ReturnType<typeof setInterval>
            }
            return realSetInterval(callback, delay)
        })
        vi.spyOn(global, 'clearInterval').mockImplementation(() => {})
        global.fetch = vi.fn()
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    async function triggerPoll(): Promise<void> {
        if (pollCallback) {
            await act(async () => {
                await pollCallback!()
            })
        }
    }

    describe('discovery mode', () => {
        it('starts and stops polling', () => {
            const callbacks = {
                mode: 'discovery' as const,
                onAwaitingConfirmation: vi.fn(),
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            const { result } = renderHook(() => useScanPolling(callbacks))

            result.current.startPolling('scan-1')
            expect(pollCallback).not.toBeNull()

            result.current.stopPolling()
            expect(global.clearInterval).toHaveBeenCalled()
        })

        it('calls onProgress with progress data', async () => {
            const callbacks = {
                mode: 'discovery' as const,
                onAwaitingConfirmation: vi.fn(),
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            const fetchMock = vi.fn().mockResolvedValue({
                ok: true,
                json: () =>
                    Promise.resolve({ status: 'running', progress: 45, progressLabel: 'Scraping...' }),
            })
            global.fetch = fetchMock

            const { result } = renderHook(() => useScanPolling(callbacks))
            result.current.startPolling('scan-1')

            await triggerPoll()

            expect(callbacks.onProgress).toHaveBeenCalledWith(45, 'Scraping...')
        })

        it('calls onAwaitingConfirmation when status is awaiting_confirmation', async () => {
            const callbacks = {
                mode: 'discovery' as const,
                onAwaitingConfirmation: vi.fn(),
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            const fetchMock = vi.fn().mockResolvedValue({
                ok: true,
                json: () =>
                    Promise.resolve({
                        status: 'awaiting_confirmation',
                        portfolioCompanies: [{ name: 'Acme', url: 'https://acme.com', description: 'Corp' }],
                    }),
            })
            global.fetch = fetchMock

            const { result } = renderHook(() => useScanPolling(callbacks))
            result.current.startPolling('scan-1')

            await triggerPoll()

            expect(callbacks.onAwaitingConfirmation).toHaveBeenCalledWith([
                { name: 'Acme', url: 'https://acme.com', description: 'Corp', selected: true },
            ])
            expect(global.clearInterval).toHaveBeenCalled()
        })

        it('calls onComplete when status is complete', async () => {
            const callbacks = {
                mode: 'discovery' as const,
                onAwaitingConfirmation: vi.fn(),
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            const responseData = {
                status: 'complete',
                analyses: [{ id: 'a-1', analyzedAt: '2026-01-01' }],
            }
            const fetchMock = vi.fn().mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(responseData),
            })
            global.fetch = fetchMock

            const { result } = renderHook(() => useScanPolling(callbacks))
            result.current.startPolling('scan-1')

            await triggerPoll()

            expect(callbacks.onComplete).toHaveBeenCalledWith(responseData)
            expect(global.clearInterval).toHaveBeenCalled()
        })

        it('calls onFailed when status is failed', async () => {
            const callbacks = {
                mode: 'discovery' as const,
                onAwaitingConfirmation: vi.fn(),
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            const fetchMock = vi.fn().mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ status: 'failed' }),
            })
            global.fetch = fetchMock

            const { result } = renderHook(() => useScanPolling(callbacks))
            result.current.startPolling('scan-1')

            await triggerPoll()

            expect(callbacks.onFailed).toHaveBeenCalledWith('Analysis failed. Please try again.')
            expect(global.clearInterval).toHaveBeenCalled()
        })

        it('silently retries on network error', async () => {
            const callbacks = {
                mode: 'discovery' as const,
                onAwaitingConfirmation: vi.fn(),
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            const fetchMock = vi.fn().mockRejectedValue(new Error('Network error'))
            global.fetch = fetchMock

            const { result } = renderHook(() => useScanPolling(callbacks))
            result.current.startPolling('scan-1')

            await triggerPoll()

            expect(callbacks.onFailed).not.toHaveBeenCalled()
            expect(callbacks.onComplete).not.toHaveBeenCalled()
        })

        it('skips update on non-ok response', async () => {
            const callbacks = {
                mode: 'discovery' as const,
                onAwaitingConfirmation: vi.fn(),
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            const fetchMock = vi.fn().mockResolvedValue({ ok: false })
            global.fetch = fetchMock

            const { result } = renderHook(() => useScanPolling(callbacks))
            result.current.startPolling('scan-1')

            await triggerPoll()

            expect(callbacks.onProgress).not.toHaveBeenCalled()
            expect(callbacks.onComplete).not.toHaveBeenCalled()
        })
    })

    describe('portfolio mode', () => {
        it('calculates weighted progress from analyses', async () => {
            const callbacks = {
                mode: 'portfolio' as const,
                totalCompanies: 3,
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            const fetchMock = vi.fn().mockResolvedValue({
                ok: true,
                json: () =>
                    Promise.resolve({
                        status: 'running',
                        analyses: [
                            { analyzedAt: '2026-01-01', pipelineProgress: 100 },
                            { analyzedAt: null, pipelineProgress: 50, pipelineLabel: 'Assessing risks...' },
                            { analyzedAt: null, pipelineProgress: 0 },
                        ],
                    }),
            })
            global.fetch = fetchMock

            const { result } = renderHook(() => useScanPolling(callbacks))
            result.current.startPolling('scan-1')

            await triggerPoll()

            // 1 done (100) + 1 at 50 + 1 at 0 = 150/3 = 50 avg
            // 10 + round(50 * 0.85) = 10 + 43 = 53
            expect(callbacks.onProgress).toHaveBeenCalledWith(
                53,
                'Assessing risks... (1/3 complete, 1 in progress)'
            )
        })

        it('calls onComplete when portfolio status is complete', async () => {
            const callbacks = {
                mode: 'portfolio' as const,
                totalCompanies: 2,
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            const responseData = {
                status: 'complete',
                analyses: [{ analyzedAt: '2026-01-01' }, { analyzedAt: '2026-01-01' }],
            }
            const fetchMock = vi.fn().mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(responseData),
            })
            global.fetch = fetchMock

            const { result } = renderHook(() => useScanPolling(callbacks))
            result.current.startPolling('scan-1')

            await triggerPoll()

            expect(callbacks.onComplete).toHaveBeenCalledWith(responseData)
        })

        it('calls onFailed when portfolio status is failed', async () => {
            const callbacks = {
                mode: 'portfolio' as const,
                totalCompanies: 2,
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            const fetchMock = vi.fn().mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ status: 'failed', analyses: [] }),
            })
            global.fetch = fetchMock

            const { result } = renderHook(() => useScanPolling(callbacks))
            result.current.startPolling('scan-1')

            await triggerPoll()

            expect(callbacks.onFailed).toHaveBeenCalledWith('Portfolio analysis failed.')
        })

        it('shows finishing label when all companies done', async () => {
            const callbacks = {
                mode: 'portfolio' as const,
                totalCompanies: 2,
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            const fetchMock = vi.fn().mockResolvedValue({
                ok: true,
                json: () =>
                    Promise.resolve({
                        status: 'running',
                        analyses: [{ analyzedAt: '2026-01-01' }, { analyzedAt: '2026-01-01' }],
                    }),
            })
            global.fetch = fetchMock

            const { result } = renderHook(() => useScanPolling(callbacks))
            result.current.startPolling('scan-1')

            await triggerPoll()

            expect(callbacks.onProgress).toHaveBeenCalledWith(95, 'Finishing up... (2/2 complete)')
        })
    })

    describe('cleanup', () => {
        it('clears interval on unmount', () => {
            const callbacks = {
                mode: 'discovery' as const,
                onAwaitingConfirmation: vi.fn(),
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            const { result, unmount } = renderHook(() => useScanPolling(callbacks))
            result.current.startPolling('scan-1')

            unmount()

            expect(global.clearInterval).toHaveBeenCalled()
        })
    })
})
