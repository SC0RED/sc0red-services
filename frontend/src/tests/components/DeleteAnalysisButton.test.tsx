import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

import DeleteAnalysisButton from '@/components/DeleteAnalysisButton'

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
        vi.clearAllMocks()
        global.fetch = vi.fn().mockResolvedValue({ ok: true })
    })

    it('renders icon variant by default', () => {
        render(<DeleteAnalysisButton analysisId="test-id" companyName="Acme" />)
        expect(screen.getByTitle('Delete analysis')).toBeInTheDocument()
    })

    it('renders button text when variant is "button"', () => {
        render(<DeleteAnalysisButton analysisId="test-id" companyName="Acme" variant="button" />)
        expect(screen.getByText('Delete Analysis')).toBeInTheDocument()
    })

    it('shows confirm UI after clicking icon', () => {
        render(<DeleteAnalysisButton analysisId="test-id" companyName="Acme Corp" />)
        fireEvent.click(screen.getByTitle('Delete analysis'))
        expect(screen.getByText('Delete?')).toBeInTheDocument()
        expect(screen.getByText('Yes')).toBeInTheDocument()
        expect(screen.getByText('No')).toBeInTheDocument()
    })

    it('returns to initial icon state when No is clicked', () => {
        render(<DeleteAnalysisButton analysisId="test-id" companyName="Acme" />)
        fireEvent.click(screen.getByTitle('Delete analysis'))
        fireEvent.click(screen.getByText('No'))
        expect(screen.getByTitle('Delete analysis')).toBeInTheDocument()
    })

    it('calls fetch DELETE and router.refresh on confirm', async () => {
        render(<DeleteAnalysisButton analysisId="test-id" companyName="Acme" />)
        fireEvent.click(screen.getByTitle('Delete analysis'))
        fireEvent.click(screen.getByText('Yes'))

        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalledWith('/api/analysis/test-id', { method: 'DELETE' })
            expect(mockRefresh).toHaveBeenCalled()
        })
    })

    it('calls router.push with redirectTo when provided', async () => {
        render(<DeleteAnalysisButton analysisId="test-id" companyName="Acme" redirectTo="/analyses" />)
        fireEvent.click(screen.getByTitle('Delete analysis'))
        fireEvent.click(screen.getByText('Yes'))

        await waitFor(() => {
            expect(mockPush).toHaveBeenCalledWith('/analyses')
        })
    })

    it('shows "..." text while the request is in-flight', async () => {
        global.fetch = vi.fn().mockImplementation(() => new Promise(() => {}))

        render(<DeleteAnalysisButton analysisId="test-id" companyName="Acme" />)
        fireEvent.click(screen.getByTitle('Delete analysis'))
        fireEvent.click(screen.getByText('Yes'))

        await waitFor(() => {
            expect(screen.getByText('...')).toBeInTheDocument()
        })
    })
})
