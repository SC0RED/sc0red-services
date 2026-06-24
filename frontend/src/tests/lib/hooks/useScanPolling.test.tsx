import { renderHook, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

import { useScanPolling } from '@/lib/hooks/useScanPolling'

describe('useScanPolling', () => {
    beforeEach(() => {
        vi.useFakeTimers()
        global.fetch = vi.fn()
    })

    afterEach(() => {
        vi.useRealTimers()
        vi.restoreAllMocks()
    })

    async function advanceAndFlush(ms: number) {
        await act(async () => {
            vi.advanceTimersByTime(ms)
            await Promise.resolve()
        })
    }

    describe('discovery mode', () => {
        it('starts and stops polling', async () => {
            const callbacks = {
                mode: 'discovery' as const,
                onAwaitingConfirmation: vi.fn(),
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            const { result } = renderHook(() => useScanPolling(callbacks))

            act(() => {
                result.current.startPolling('scan-1')
            })

            act(() => {
                result.current.stopPolling()
            })

            // After stop, advancing timers should not trigger any fetch
            await advanceAndFlush(5000)
            expect(global.fetch).not.toHaveBeenCalled()
        })

        it('calls onProgress with progress data', async () => {
            const callbacks = {
                mode: 'discovery' as const,
                onAwaitingConfirmation: vi.fn(),
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () =>
                    Promise.resolve({ status: 'running', progress: 45, progressLabel: 'Scraping...' }),
            })

            const { result } = renderHook(() => useScanPolling(callbacks))
            act(() => {
                result.current.startPolling('scan-1')
            })

            await advanceAndFlush(1000)

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

            ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () =>
                    Promise.resolve({
                        status: 'awaiting_confirmation',
                        portfolioCompanies: [{ name: 'Acme', url: 'https://acme.com', description: 'Corp' }],
                    }),
            })

            const { result } = renderHook(() => useScanPolling(callbacks))
            act(() => {
                result.current.startPolling('scan-1')
            })

            await advanceAndFlush(1000)

            expect(callbacks.onAwaitingConfirmation).toHaveBeenCalledWith(
                [{ name: 'Acme', url: 'https://acme.com', description: 'Corp', selected: true }],
                undefined
            )
        })

        it('does not pre-select web-search companies', async () => {
            const callbacks = {
                mode: 'discovery' as const,
                onAwaitingConfirmation: vi.fn(),
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }
            ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () =>
                    Promise.resolve({
                        status: 'awaiting_confirmation',
                        portfolioCompanies: [
                            { name: 'Site', url: 'https://site.com', description: '', source: 'site' },
                            { name: 'Web', url: 'https://web.com', description: '', source: 'web_search' },
                        ],
                    }),
            })

            const { result } = renderHook(() => useScanPolling(callbacks))
            act(() => {
                result.current.startPolling('scan-1')
            })
            await advanceAndFlush(1000)

            const companies = callbacks.onAwaitingConfirmation.mock.calls[0][0]
            expect(companies.find((c: { name: string }) => c.name === 'Site').selected).toBe(true)
            expect(companies.find((c: { name: string }) => c.name === 'Web').selected).toBe(false)
        })

        it('forwards the discovery verdict to onAwaitingConfirmation', async () => {
            const callbacks = {
                mode: 'discovery' as const,
                onAwaitingConfirmation: vi.fn(),
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }
            const verdict = {
                method: 'web_search',
                count: 3,
                completeness: 'web_search_subset' as const,
                availableActions: ['search_deeper', 'upload_list'] as const,
            }
            ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () =>
                    Promise.resolve({
                        status: 'awaiting_confirmation',
                        portfolioCompanies: [],
                        discoveryVerdict: verdict,
                    }),
            })

            const { result } = renderHook(() => useScanPolling(callbacks))
            act(() => {
                result.current.startPolling('scan-1')
            })
            await advanceAndFlush(1000)

            expect(callbacks.onAwaitingConfirmation).toHaveBeenCalledWith([], verdict)
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
            ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(responseData),
            })

            const { result } = renderHook(() => useScanPolling(callbacks))
            act(() => {
                result.current.startPolling('scan-1')
            })

            await advanceAndFlush(1000)

            expect(callbacks.onComplete).toHaveBeenCalledWith(responseData)
        })

        it('calls onFailed when status is failed', async () => {
            const callbacks = {
                mode: 'discovery' as const,
                onAwaitingConfirmation: vi.fn(),
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ status: 'failed' }),
            })

            const { result } = renderHook(() => useScanPolling(callbacks))
            act(() => {
                result.current.startPolling('scan-1')
            })

            await advanceAndFlush(1000)

            expect(callbacks.onFailed).toHaveBeenCalledWith('Analysis failed. Please try again.')
        })

        it('surfaces backend error message when status is failed', async () => {
            const callbacks = {
                mode: 'discovery' as const,
                onAwaitingConfirmation: vi.fn(),
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () =>
                    Promise.resolve({
                        status: 'failed',
                        error: 'Could not scrape website',
                    }),
            })

            const { result } = renderHook(() => useScanPolling(callbacks))
            act(() => {
                result.current.startPolling('scan-1')
            })

            await advanceAndFlush(1000)

            expect(callbacks.onFailed).toHaveBeenCalledWith('Could not scrape website')
        })

        it('continues polling while status is discovering', async () => {
            const callbacks = {
                mode: 'discovery' as const,
                onAwaitingConfirmation: vi.fn(),
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () =>
                    Promise.resolve({
                        status: 'discovering',
                        progress: 10,
                        progressLabel: 'Finding portfolio companies...',
                    }),
            })

            const { result } = renderHook(() => useScanPolling(callbacks))
            act(() => {
                result.current.startPolling('scan-1')
            })

            await advanceAndFlush(1000)

            expect(callbacks.onProgress).toHaveBeenCalledWith(10, 'Finding portfolio companies...')
            // Still discovering → none of the terminal callbacks fire.
            expect(callbacks.onAwaitingConfirmation).not.toHaveBeenCalled()
            expect(callbacks.onComplete).not.toHaveBeenCalled()
            expect(callbacks.onFailed).not.toHaveBeenCalled()
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

            ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
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

            const { result } = renderHook(() => useScanPolling(callbacks))
            act(() => {
                result.current.startPolling('scan-1')
            })

            await advanceAndFlush(1000)

            const progressCall = callbacks.onProgress.mock.calls[0]
            expect(progressCall[0]).toBe(53)
            expect(progressCall[1]).toBe('Assessing risks... (1/3 complete, 1 in progress)')
            // Third arg is the raw poll data — portfolio callers use this to
            // detect first-company-complete for early navigation.
            expect(progressCall[2]).toBeDefined()
            expect(progressCall[2].analyses).toHaveLength(3)
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
            ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(responseData),
            })

            const { result } = renderHook(() => useScanPolling(callbacks))
            act(() => {
                result.current.startPolling('scan-1')
            })

            await advanceAndFlush(1000)

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

            ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ status: 'failed', analyses: [] }),
            })

            const { result } = renderHook(() => useScanPolling(callbacks))
            act(() => {
                result.current.startPolling('scan-1')
            })

            await advanceAndFlush(1000)

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

            ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () =>
                    Promise.resolve({
                        status: 'running',
                        analyses: [{ analyzedAt: '2026-01-01' }, { analyzedAt: '2026-01-01' }],
                    }),
            })

            const { result } = renderHook(() => useScanPolling(callbacks))
            act(() => {
                result.current.startPolling('scan-1')
            })

            await advanceAndFlush(1000)

            const progressCall = callbacks.onProgress.mock.calls[0]
            expect(progressCall[0]).toBe(95)
            expect(progressCall[1]).toBe('Finishing up... (2/2 complete)')
            expect(progressCall[2]).toBeDefined()
        })
    })

    describe('cleanup', () => {
        it('clears timeout on unmount', () => {
            const callbacks = {
                mode: 'discovery' as const,
                onAwaitingConfirmation: vi.fn(),
                onComplete: vi.fn(),
                onFailed: vi.fn(),
                onProgress: vi.fn(),
            }

            const { result, unmount } = renderHook(() => useScanPolling(callbacks))
            act(() => {
                result.current.startPolling('scan-1')
            })

            unmount()

            // No pending timers should fire after unmount
            expect(() => vi.advanceTimersByTime(5000)).not.toThrow()
        })
    })
})
