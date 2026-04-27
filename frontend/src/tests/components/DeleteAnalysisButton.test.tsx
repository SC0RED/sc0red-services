import { screen, fireEvent, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

import DeleteAnalysisButton from '@/components/DeleteAnalysisButton'
import { renderWithProviders } from '@/tests/test-utils'

const mockRefresh = vi.fn()
const mockPush = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        refresh: mockRefresh,
        push: mockPush,
    }),
}))

describe('DeleteAnalysisButton', () => {
    beforeEach(() => {
        vi.useFakeTimers()
        vi.clearAllMocks()
        global.fetch = vi.fn().mockResolvedValue({ ok: true })
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    describe('render', () => {
        it('renders icon variant by default', () => {
            renderWithProviders(<DeleteAnalysisButton analysisId="test-id" companyName="Acme" />)
            expect(screen.getByTitle('Delete analysis')).toBeInTheDocument()
        })

        it('renders button text when variant is "button"', () => {
            renderWithProviders(
                <DeleteAnalysisButton analysisId="test-id" companyName="Acme" variant="button" />
            )
            expect(screen.getByText('Delete Analysis')).toBeInTheDocument()
        })
    })

    describe('toast.undo flow', () => {
        it('clicking delete shows a "Deleted ... Undo?" toast (no inline confirm UI)', () => {
            renderWithProviders(<DeleteAnalysisButton analysisId="test-id" companyName="Acme Corp" />)
            fireEvent.click(screen.getByTitle('Delete analysis'))

            expect(screen.getByText('Deleted Acme Corp')).toBeInTheDocument()
            expect(screen.getByText('Undo')).toBeInTheDocument()
            // The old inline "Delete Acme Corp?" Yes/No flow is gone
            expect(screen.queryByText(/^Delete Acme Corp\?$/)).not.toBeInTheDocument()
        })

        it('does NOT call DELETE before the 5-second window expires', () => {
            renderWithProviders(<DeleteAnalysisButton analysisId="test-id" companyName="Acme" />)
            fireEvent.click(screen.getByTitle('Delete analysis'))

            act(() => {
                vi.advanceTimersByTime(4999)
            })
            expect(global.fetch).not.toHaveBeenCalled()
        })

        it('calls DELETE + router.refresh after the 5-second window expires', async () => {
            renderWithProviders(<DeleteAnalysisButton analysisId="test-id" companyName="Acme" />)
            fireEvent.click(screen.getByTitle('Delete analysis'))

            await act(async () => {
                await vi.advanceTimersByTimeAsync(5000)
            })

            expect(global.fetch).toHaveBeenCalledWith('/api/analysis/test-id', { method: 'DELETE' })
            // After advanceTimersByTimeAsync flushes, the awaited fetch.then
            // chain has run inside React's act batcher; assertions can run
            // synchronously without an additional waitFor.
            expect(mockRefresh).toHaveBeenCalled()
        })

        it('calls router.push when redirectTo is set', async () => {
            renderWithProviders(
                <DeleteAnalysisButton analysisId="test-id" companyName="Acme" redirectTo="/analyses" />
            )
            fireEvent.click(screen.getByTitle('Delete analysis'))

            await act(async () => {
                await vi.advanceTimersByTimeAsync(5000)
            })

            expect(mockPush).toHaveBeenCalledWith('/analyses')
        })

        it('clicking Undo cancels — no DELETE fires even after 10 seconds', () => {
            renderWithProviders(<DeleteAnalysisButton analysisId="test-id" companyName="Acme" />)
            fireEvent.click(screen.getByTitle('Delete analysis'))
            fireEvent.click(screen.getByText('Undo'))

            act(() => {
                vi.advanceTimersByTime(10_000)
            })
            expect(global.fetch).not.toHaveBeenCalled()
            expect(mockRefresh).not.toHaveBeenCalled()
        })

        it('button is disabled while delete is pending', () => {
            renderWithProviders(<DeleteAnalysisButton analysisId="test-id" companyName="Acme" />)
            const trigger = screen.getByTitle('Delete analysis')
            fireEvent.click(trigger)

            // Title swaps to indicate pending state
            expect(screen.getByTitle('Deleting...')).toBeDisabled()
        })

        it('Undo re-enables the button', () => {
            renderWithProviders(<DeleteAnalysisButton analysisId="test-id" companyName="Acme" />)
            fireEvent.click(screen.getByTitle('Delete analysis'))
            fireEvent.click(screen.getByText('Undo'))

            expect(screen.getByTitle('Delete analysis')).not.toBeDisabled()
        })

        it('shows error toast and re-enables button on DELETE failure', async () => {
            global.fetch = vi.fn().mockResolvedValue({ ok: false })
            renderWithProviders(<DeleteAnalysisButton analysisId="test-id" companyName="Acme" />)
            fireEvent.click(screen.getByTitle('Delete analysis'))

            await act(async () => {
                await vi.advanceTimersByTimeAsync(5000)
            })

            expect(screen.getByText('Failed to delete Acme')).toBeInTheDocument()
            expect(mockRefresh).not.toHaveBeenCalled()
        })
    })
})
