import { fireEvent, screen, waitFor, act } from '@testing-library/react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

import ExportPDFButton from '@/components/analysis/ExportPDFButton'
import { renderWithProviders } from '@/tests/test-utils'

/**
 * Helpers for the async PDF export flow.
 *
 *   POST /api/export/pdf/<id>            → 200 ready | 202 rendering | 5xx
 *   GET  /api/export/pdf/<id>/status     → 200 {status: rendering|ready|failed}
 *
 * The button always POSTs first, then polls only on 202.
 *
 * Timing pattern: ``waitFor`` uses real ``setTimeout`` for its internal
 * retries — under ``vi.useFakeTimers()`` it never fires, so tests that
 * fake timers must use direct ``expect`` after explicit microtask
 * flushes (multiple ``await act(...)`` blocks). Helper below.
 */

function jsonResponse(body: unknown, status = 200): Response {
    return new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
    })
}

/**
 * Flush React state updates + pending microtasks (e.g., promise
 * resolutions chained through ``await fetch`` → ``await res.json()`` →
 * ``setState`` → ``setTimeout``). Multiple flushes handle deeper chains.
 * Safe under both real and fake timers — ``Promise.resolve()`` is not
 * mocked by ``vi.useFakeTimers``.
 */
async function flushMicrotasks(times = 5): Promise<void> {
    for (let i = 0; i < times; i++) {
        await act(async () => {
            await Promise.resolve()
        })
    }
}

const ANALYSIS_ID = 'a-1'
const PRESIGNED_URL = 'https://s3.example.com/pdf-exports/a-1.pdf?sig=abc'

beforeEach(() => {
    vi.useRealTimers()
})

afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
})

describe('ExportPDFButton — idle state', () => {
    it('renders idle by default with the default label', () => {
        renderWithProviders(<ExportPDFButton analysisId={ANALYSIS_ID} />)
        const btn = screen.getByRole('button', { name: /Export PDF/i })
        expect(btn).toBeEnabled()
        expect(btn).toHaveAttribute('aria-busy', 'false')
    })

    it('does not stack a second request when the user clicks while loading', async () => {
        // Make the POST hang so the button stays in the polling-or-loading state.
        const fetchMock = vi.fn().mockImplementation(() => new Promise(() => {}))
        global.fetch = fetchMock

        renderWithProviders(<ExportPDFButton analysisId={ANALYSIS_ID} />)
        const btn = screen.getByRole('button')
        fireEvent.click(btn)
        fireEvent.click(btn)
        fireEvent.click(btn)
        expect(fetchMock).toHaveBeenCalledTimes(1)
    })
})

describe('ExportPDFButton — cached path (POST returns 200 ready)', () => {
    it('triggers download to the presigned URL with no polling', async () => {
        global.fetch = vi
            .fn()
            .mockResolvedValue(
                jsonResponse({ status: 'ready', url: PRESIGNED_URL, generatedAt: '2026-05-18T10:00:13Z' })
            )
        const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

        renderWithProviders(<ExportPDFButton analysisId={ANALYSIS_ID} />)
        fireEvent.click(screen.getByRole('button'))

        await waitFor(() => expect(clickSpy).toHaveBeenCalled())
        const anchor = clickSpy.mock.instances[0] as unknown as HTMLAnchorElement
        expect(anchor.href).toBe(PRESIGNED_URL)
        expect(anchor.rel).toBe('noopener')

        // Cached path returns immediately to idle — no polling toast.
        expect(screen.getByRole('button', { name: /Export PDF/i })).toBeEnabled()
        // Only one fetch (the POST). No status polling.
        expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls).toHaveLength(1)
    })
})

describe('ExportPDFButton — cold path (POST returns 202 rendering)', () => {
    it('enters polling state, then downloads when status flips to ready', async () => {
        vi.useFakeTimers()
        const fetchMock = vi
            .fn()
            // POST → 202 rendering
            .mockResolvedValueOnce(
                jsonResponse({ status: 'rendering', startedAt: '2026-05-18T10:00:00Z' }, 202)
            )
            // First status poll → still rendering
            .mockResolvedValueOnce(jsonResponse({ status: 'rendering', startedAt: '2026-05-18T10:00:00Z' }))
            // Second status poll → ready
            .mockResolvedValueOnce(
                jsonResponse({ status: 'ready', url: PRESIGNED_URL, generatedAt: '2026-05-18T10:00:13Z' })
            )
        global.fetch = fetchMock
        const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

        renderWithProviders(<ExportPDFButton analysisId={ANALYSIS_ID} />)
        fireEvent.click(screen.getByRole('button'))
        await flushMicrotasks()

        // Loading toast is up; button is disabled. Both the button and
        // the toast carry the "Generating PDF" text, so use getAllByText
        // and assert there are 2 (toast + button label).
        expect(screen.getAllByText(/Generating PDF/i).length).toBeGreaterThanOrEqual(2)

        // Tick the first poll (2s) → still rendering.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(2_000)
        })
        // Tick the second poll (2s) → ready.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(2_000)
        })
        await flushMicrotasks()

        expect(clickSpy).toHaveBeenCalled()
        const anchor = clickSpy.mock.instances[0] as unknown as HTMLAnchorElement
        expect(anchor.href).toBe(PRESIGNED_URL)

        // 3 fetches total: 1 POST + 2 status polls.
        expect(fetchMock).toHaveBeenCalledTimes(3)
        expect(fetchMock.mock.calls[0][0]).toBe(`/api/export/pdf/${ANALYSIS_ID}`)
        expect(fetchMock.mock.calls[1][0]).toBe(`/api/export/pdf/${ANALYSIS_ID}/status`)
        expect(fetchMock.mock.calls[2][0]).toBe(`/api/export/pdf/${ANALYSIS_ID}/status`)
    })

    it('shows an error Toast and returns to idle when polling sees status: failed', async () => {
        vi.useFakeTimers()
        global.fetch = vi
            .fn()
            .mockResolvedValueOnce(
                jsonResponse({ status: 'rendering', startedAt: '2026-05-18T10:00:00Z' }, 202)
            )
            .mockResolvedValueOnce(jsonResponse({ status: 'failed', error: 'Puppeteer crashed mid-render' }))

        renderWithProviders(<ExportPDFButton analysisId={ANALYSIS_ID} />)
        fireEvent.click(screen.getByRole('button'))
        await flushMicrotasks()

        await act(async () => {
            await vi.advanceTimersByTimeAsync(2_000)
        })
        await flushMicrotasks()

        expect(screen.getByText(/Puppeteer crashed mid-render/i)).toBeInTheDocument()
        // Button back to idle.
        expect(screen.getByRole('button', { name: /Export PDF/i })).toBeEnabled()
    })

    it('treats synthetic stale-rendering (status: failed with "stuck" error) as a normal failed flow', async () => {
        vi.useFakeTimers()
        global.fetch = vi
            .fn()
            .mockResolvedValueOnce(
                jsonResponse({ status: 'rendering', startedAt: '2026-05-18T10:00:00Z' }, 202)
            )
            .mockResolvedValueOnce(
                jsonResponse({ status: 'failed', error: 'Render appears stuck; try again.' })
            )

        renderWithProviders(<ExportPDFButton analysisId={ANALYSIS_ID} />)
        fireEvent.click(screen.getByRole('button'))
        await flushMicrotasks()

        await act(async () => {
            await vi.advanceTimersByTimeAsync(2_000)
        })
        await flushMicrotasks()

        expect(screen.getByText(/stuck/i)).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /Export PDF/i })).toBeEnabled()
    })

    it('treats status: none (re-analyse race) as a cancellation', async () => {
        vi.useFakeTimers()
        global.fetch = vi
            .fn()
            .mockResolvedValueOnce(
                jsonResponse({ status: 'rendering', startedAt: '2026-05-18T10:00:00Z' }, 202)
            )
            .mockResolvedValueOnce(jsonResponse({ status: 'none' }))

        renderWithProviders(<ExportPDFButton analysisId={ANALYSIS_ID} />)
        fireEvent.click(screen.getByRole('button'))
        await flushMicrotasks()

        await act(async () => {
            await vi.advanceTimersByTimeAsync(2_000)
        })
        await flushMicrotasks()

        expect(screen.getByText(/cancelled by re-analyse/i)).toBeInTheDocument()
    })
})

describe('ExportPDFButton — poll cadence', () => {
    it('uses 2-second intervals for the first 10 polls, then 5-second intervals', async () => {
        vi.useFakeTimers()
        const responses: Response[] = [
            jsonResponse({ status: 'rendering', startedAt: '2026-05-18T10:00:00Z' }, 202),
        ]
        for (let i = 0; i < 20; i++) {
            responses.push(jsonResponse({ status: 'rendering', startedAt: '2026-05-18T10:00:00Z' }))
        }
        const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(responses.shift()!))
        global.fetch = fetchMock

        renderWithProviders(<ExportPDFButton analysisId={ANALYSIS_ID} />)
        fireEvent.click(screen.getByRole('button'))
        await flushMicrotasks()
        // 1 fetch: the POST.
        expect(fetchMock).toHaveBeenCalledTimes(1)

        // 10 polls at FAST (2 s each).
        for (let i = 1; i <= 10; i++) {
            await act(async () => {
                await vi.advanceTimersByTimeAsync(2_000)
            })
            await flushMicrotasks()
            expect(fetchMock).toHaveBeenCalledTimes(1 + i)
        }

        // After 10 polls, the next scheduled interval is SLOW (5 s).
        // Advancing 2 s should NOT fire it; advancing the remaining 3 s should.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(2_000)
        })
        await flushMicrotasks()
        expect(fetchMock).toHaveBeenCalledTimes(11) // unchanged — still under SLOW interval

        await act(async () => {
            await vi.advanceTimersByTimeAsync(3_000)
        })
        await flushMicrotasks()
        expect(fetchMock).toHaveBeenCalledTimes(12) // slow tick fired
    })
})

describe('ExportPDFButton — POST failure', () => {
    it('shows a Toast and resets to idle on POST HTTP 5xx', async () => {
        global.fetch = vi.fn().mockResolvedValue(new Response('boom', { status: 500 }))

        renderWithProviders(<ExportPDFButton analysisId={ANALYSIS_ID} />)
        fireEvent.click(screen.getByRole('button'))

        await waitFor(() => {
            expect(screen.getByText(/HTTP 500/)).toBeInTheDocument()
        })
        expect(screen.getByRole('button', { name: /Export PDF/i })).toBeEnabled()
    })

    it('shows a Toast on network failure during POST', async () => {
        global.fetch = vi.fn().mockRejectedValue(new Error('network down'))

        renderWithProviders(<ExportPDFButton analysisId={ANALYSIS_ID} />)
        fireEvent.click(screen.getByRole('button'))

        await waitFor(() => {
            expect(screen.getByText('network down')).toBeInTheDocument()
        })
        expect(screen.getByRole('button', { name: /Export PDF/i })).toBeEnabled()
    })

    it('shows a Toast when POST returns 5xx with status: failed (synchronous failure)', async () => {
        // The Next.js POST handler returns HTTP 500 when the backend
        // reports ``status: 'failed'``, so access logs / monitoring see
        // the failure. The button surfaces the HTTP code in the toast.
        global.fetch = vi
            .fn()
            .mockResolvedValue(jsonResponse({ status: 'failed', error: 'PDF export failed to enqueue' }, 500))

        renderWithProviders(<ExportPDFButton analysisId={ANALYSIS_ID} />)
        fireEvent.click(screen.getByRole('button'))

        await waitFor(() => {
            expect(screen.getByText(/HTTP 500/)).toBeInTheDocument()
        })
    })
})

describe('ExportPDFButton — polling resilience', () => {
    it('tolerates transient status-endpoint failures up to the consecutive-failure cap', async () => {
        vi.useFakeTimers()
        const fetchMock = vi
            .fn()
            .mockResolvedValueOnce(
                jsonResponse({ status: 'rendering', startedAt: '2026-05-18T10:00:00Z' }, 202)
            )
            .mockRejectedValueOnce(new Error('transient 1'))
            .mockRejectedValueOnce(new Error('transient 2'))
            .mockRejectedValueOnce(new Error('transient 3'))
            .mockResolvedValueOnce(jsonResponse({ status: 'ready', url: PRESIGNED_URL }))
        global.fetch = fetchMock
        const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

        renderWithProviders(<ExportPDFButton analysisId={ANALYSIS_ID} />)
        fireEvent.click(screen.getByRole('button'))
        await flushMicrotasks()

        // 4 polls × 2 s each → 3 failures then ready.
        for (let i = 0; i < 4; i++) {
            await act(async () => {
                await vi.advanceTimersByTimeAsync(2_000)
            })
            await flushMicrotasks()
        }

        expect(clickSpy).toHaveBeenCalled()
    })

    it('bails with an error Toast after 5 consecutive status-endpoint failures', async () => {
        vi.useFakeTimers()
        const responses: Response[] = [
            jsonResponse({ status: 'rendering', startedAt: '2026-05-18T10:00:00Z' }, 202),
        ]
        const fetchMock = vi.fn().mockImplementation(() => {
            if (responses.length > 0) return Promise.resolve(responses.shift()!)
            return Promise.reject(new Error('persistent outage'))
        })
        global.fetch = fetchMock

        renderWithProviders(<ExportPDFButton analysisId={ANALYSIS_ID} />)
        fireEvent.click(screen.getByRole('button'))
        await flushMicrotasks()

        // 5 polls × 2 s each → consecutive-failure cap reached.
        for (let i = 0; i < 5; i++) {
            await act(async () => {
                await vi.advanceTimersByTimeAsync(2_000)
            })
            await flushMicrotasks()
        }

        expect(screen.getByText(/persistent outage/i)).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /Export PDF/i })).toBeEnabled()
    })
})
