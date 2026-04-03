import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

import DeleteScanButton from '@/components/DeleteScanButton'

const mockRefresh = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        refresh: mockRefresh,
    }),
}))

describe('DeleteScanButton', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        global.fetch = vi.fn().mockResolvedValue({ ok: true })
    })

    it('renders trash icon button by default', () => {
        render(<DeleteScanButton scanId="scan-1" />)
        expect(screen.getByTitle('Delete scan')).toBeInTheDocument()
    })

    it('shows confirm UI after clicking icon', () => {
        render(<DeleteScanButton scanId="scan-1" />)
        fireEvent.click(screen.getByTitle('Delete scan'))
        expect(screen.getByText('Delete')).toBeInTheDocument()
        expect(screen.getByText('Cancel')).toBeInTheDocument()
    })

    it('returns to initial icon state when Cancel is clicked', () => {
        render(<DeleteScanButton scanId="scan-1" />)
        fireEvent.click(screen.getByTitle('Delete scan'))
        fireEvent.click(screen.getByText('Cancel'))
        expect(screen.getByTitle('Delete scan')).toBeInTheDocument()
    })

    it('calls fetch DELETE and router.refresh on confirm', async () => {
        render(<DeleteScanButton scanId="scan-1" />)
        fireEvent.click(screen.getByTitle('Delete scan'))
        fireEvent.click(screen.getByText('Delete'))

        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalledWith('/api/scan/scan-1', { method: 'DELETE' })
            expect(mockRefresh).toHaveBeenCalled()
        })
    })

    it('shows "Deleting..." text while the request is in-flight', async () => {
        global.fetch = vi.fn().mockImplementation(() => new Promise(() => {}))

        render(<DeleteScanButton scanId="scan-1" />)
        fireEvent.click(screen.getByTitle('Delete scan'))
        fireEvent.click(screen.getByText('Delete'))

        await waitFor(() => {
            expect(screen.getByText('Deleting...')).toBeInTheDocument()
        })
    })
})
