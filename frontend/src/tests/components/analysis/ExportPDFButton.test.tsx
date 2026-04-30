import { fireEvent, screen, waitFor, act } from '@testing-library/react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

import ExportPDFButton from '@/components/analysis/ExportPDFButton'
import { renderWithProviders } from '@/tests/test-utils'

const PDF_BYTES = new Uint8Array([0x25, 0x50, 0x44, 0x46]) // %PDF magic

function buildPdfResponse({
    contentDisposition = 'attachment; filename="Acme - AI Risk Report - 2026-04-30.pdf"',
}: { contentDisposition?: string } = {}): Response {
    const blob = new Blob([PDF_BYTES], { type: 'application/pdf' })
    return new Response(blob, {
        status: 200,
        headers: {
            'Content-Type': 'application/pdf',
            'Content-Disposition': contentDisposition,
        },
    })
}

const originalCreateObjectURL = URL.createObjectURL
const originalRevokeObjectURL = URL.revokeObjectURL

beforeEach(() => {
    URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-url')
    URL.revokeObjectURL = vi.fn()
})

afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    URL.createObjectURL = originalCreateObjectURL
    URL.revokeObjectURL = originalRevokeObjectURL
})

describe('ExportPDFButton', () => {
    it('renders idle by default with the default label', () => {
        renderWithProviders(<ExportPDFButton analysisId="a-1" />)
        const btn = screen.getByRole('button', { name: /Export PDF/i })
        expect(btn).toBeEnabled()
        expect(btn).toHaveAttribute('aria-busy', 'false')
    })

    it('shows "Generating PDF…" within 200ms after click', async () => {
        vi.useFakeTimers()
        global.fetch = vi.fn().mockImplementation(
            () => new Promise(() => {}) // never resolves so we can observe loading
        )
        renderWithProviders(<ExportPDFButton analysisId="a-1" />)
        const btn = screen.getByRole('button', { name: /Export PDF/i })

        fireEvent.click(btn)
        // Pre-threshold: button is "starting" but label still shows the in-flight text
        // because state !== 'idle' triggers the loading branch.
        expect(btn).toBeDisabled()
        expect(btn).toHaveAttribute('aria-busy', 'true')

        await act(async () => {
            await vi.advanceTimersByTimeAsync(250)
        })
        expect(screen.getByRole('button')).toHaveTextContent(/Generating PDF/i)
    })

    it('flips to "Still working…" after 5 seconds', async () => {
        vi.useFakeTimers()
        global.fetch = vi.fn().mockImplementation(() => new Promise(() => {}))
        renderWithProviders(<ExportPDFButton analysisId="a-1" />)
        fireEvent.click(screen.getByRole('button'))

        await act(async () => {
            await vi.advanceTimersByTimeAsync(5_100)
        })
        expect(screen.getByRole('button')).toHaveTextContent(/Still working/i)
    })

    it('triggers a download with the Content-Disposition filename on success', async () => {
        global.fetch = vi.fn().mockResolvedValue(buildPdfResponse())
        const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

        renderWithProviders(<ExportPDFButton analysisId="a-1" />)
        fireEvent.click(screen.getByRole('button'))

        // Real timers; just await the microtask queue.
        await Promise.resolve()
        await waitFor(() => expect(clickSpy).toHaveBeenCalled())

        // The anchor that was clicked should carry the filename from the header.
        const calls = clickSpy.mock.instances
        expect(calls.length).toBeGreaterThan(0)
        const anchor = calls[0] as unknown as HTMLAnchorElement
        expect(anchor.download).toBe('Acme - AI Risk Report - 2026-04-30.pdf')

        // Object URL is revoked after the download fires.
        await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url'))
    })

    it('falls back to a generic filename when the header is absent', async () => {
        global.fetch = vi.fn().mockResolvedValue(new Response(new Blob(), { status: 200, headers: {} }))
        const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

        renderWithProviders(<ExportPDFButton analysisId="abc-123" />)
        fireEvent.click(screen.getByRole('button'))
        // Real timers; just await the microtask queue.
        await Promise.resolve()
        await waitFor(() => expect(clickSpy).toHaveBeenCalled())

        const anchor = clickSpy.mock.instances[0] as unknown as HTMLAnchorElement
        expect(anchor.download).toBe('analysis-abc-123.pdf')
    })

    it('shows a Toast and resets to idle on HTTP error', async () => {
        global.fetch = vi.fn().mockResolvedValue(new Response('boom', { status: 500 }))

        renderWithProviders(<ExportPDFButton analysisId="a-1" />)
        fireEvent.click(screen.getByRole('button'))

        // Real timers; just await the microtask queue.
        await Promise.resolve()

        await waitFor(() => {
            expect(screen.getByText(/PDF export failed.*HTTP 500/)).toBeInTheDocument()
        })
        expect(screen.getByRole('button', { name: /Export PDF/i })).toBeEnabled()
    })

    it('shows a Toast on network failure', async () => {
        global.fetch = vi.fn().mockRejectedValue(new Error('network down'))

        renderWithProviders(<ExportPDFButton analysisId="a-1" />)
        fireEvent.click(screen.getByRole('button'))

        // Real timers; just await the microtask queue.
        await Promise.resolve()

        await waitFor(() => {
            expect(screen.getByText('network down')).toBeInTheDocument()
        })
        expect(screen.getByRole('button', { name: /Export PDF/i })).toBeEnabled()
    })

    it('does not stack a second request when the user clicks while loading', async () => {
        const fetchMock = vi.fn().mockImplementation(() => new Promise(() => {}))
        global.fetch = fetchMock

        renderWithProviders(<ExportPDFButton analysisId="a-1" />)
        const btn = screen.getByRole('button')
        fireEvent.click(btn)
        fireEvent.click(btn)
        fireEvent.click(btn)
        expect(fetchMock).toHaveBeenCalledTimes(1)
    })
})
