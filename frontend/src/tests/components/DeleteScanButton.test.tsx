import { screen, fireEvent, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

import DeleteScanButton from '@/components/DeleteScanButton'
import { renderWithProviders } from '@/tests/test-utils'

const mockRefresh = vi.fn()
const mockPush = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        refresh: mockRefresh,
        push: mockPush,
    }),
}))

describe('DeleteScanButton', () => {
    beforeEach(() => {
        vi.useFakeTimers()
        vi.clearAllMocks()
        global.fetch = vi.fn().mockResolvedValue({ ok: true })
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it('renders trash icon button by default', () => {
        renderWithProviders(<DeleteScanButton scanId="scan-1" />)
        expect(screen.getByTitle('Delete scan')).toBeInTheDocument()
    })

    it('clicking shows toast with cascade scope when companyCount provided', () => {
        renderWithProviders(<DeleteScanButton scanId="scan-1" companyCount={8} />)
        fireEvent.click(screen.getByTitle('Delete scan'))

        expect(screen.getByText('Deleted scan + 8 analyses')).toBeInTheDocument()
        expect(screen.getByText('Undo')).toBeInTheDocument()
    })

    it('uses singular "analysis" for 1 company', () => {
        renderWithProviders(<DeleteScanButton scanId="scan-1" companyCount={1} />)
        fireEvent.click(screen.getByTitle('Delete scan'))

        expect(screen.getByText('Deleted scan + 1 analysis')).toBeInTheDocument()
    })

    it('falls back to plain "Deleted scan" when companyCount is missing or zero', () => {
        renderWithProviders(<DeleteScanButton scanId="scan-1" />)
        fireEvent.click(screen.getByTitle('Delete scan'))
        expect(screen.getByText('Deleted scan')).toBeInTheDocument()
    })

    it('does NOT call DELETE before the 5-second window expires', () => {
        renderWithProviders(<DeleteScanButton scanId="scan-1" />)
        fireEvent.click(screen.getByTitle('Delete scan'))

        act(() => {
            vi.advanceTimersByTime(4999)
        })
        expect(global.fetch).not.toHaveBeenCalled()
    })

    it('calls DELETE + router.refresh after the 5-second window expires', async () => {
        renderWithProviders(<DeleteScanButton scanId="scan-1" />)
        fireEvent.click(screen.getByTitle('Delete scan'))

        await act(async () => {
            await vi.advanceTimersByTimeAsync(5000)
        })

        expect(global.fetch).toHaveBeenCalledWith('/api/scan/scan-1', { method: 'DELETE' })
        expect(mockRefresh).toHaveBeenCalled()
    })

    it('clicking Undo cancels — no DELETE fires', () => {
        renderWithProviders(<DeleteScanButton scanId="scan-1" companyCount={3} />)
        fireEvent.click(screen.getByTitle('Delete scan'))
        fireEvent.click(screen.getByText('Undo'))

        act(() => {
            vi.advanceTimersByTime(10_000)
        })
        expect(global.fetch).not.toHaveBeenCalled()
        expect(mockRefresh).not.toHaveBeenCalled()
    })

    it('shows error toast on DELETE failure', async () => {
        global.fetch = vi.fn().mockResolvedValue({ ok: false })
        renderWithProviders(<DeleteScanButton scanId="scan-1" />)
        fireEvent.click(screen.getByTitle('Delete scan'))

        await act(async () => {
            await vi.advanceTimersByTimeAsync(5000)
        })

        expect(screen.getByText('Failed to delete scan')).toBeInTheDocument()
        expect(mockRefresh).not.toHaveBeenCalled()
    })

    it('navigates to redirectTo on success instead of refreshing', async () => {
        renderWithProviders(<DeleteScanButton scanId="scan-9" redirectTo="/dashboard" />)
        fireEvent.click(screen.getByTitle('Delete scan'))

        await act(async () => {
            await vi.advanceTimersByTimeAsync(5000)
        })

        expect(global.fetch).toHaveBeenCalledWith('/api/scan/scan-9', { method: 'DELETE' })
        expect(mockPush).toHaveBeenCalledWith('/dashboard')
        expect(mockRefresh).not.toHaveBeenCalled()
    })

    it('renders the primary variant with a label and stays a single button', () => {
        renderWithProviders(<DeleteScanButton scanId="scan-1" variant="primary" label="Delete portfolio" />)
        // The variant exposes the label text in the button itself —
        // critical for the portfolio-page header where the icon-only
        // ghost would be too subtle for a top-level destructive action.
        const buttons = screen.getAllByRole('button', { name: 'Delete portfolio' })
        expect(buttons).toHaveLength(1)
        expect(buttons[0]).toHaveTextContent('Delete portfolio')
    })
})
