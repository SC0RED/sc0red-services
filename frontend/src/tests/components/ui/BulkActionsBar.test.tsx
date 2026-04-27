import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import BulkActionsBar from '@/components/ui/BulkActionsBar'
import { renderWithProviders as render } from '@/tests/test-utils'

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
    usePathname: () => '/analyses',
}))

describe('BulkActionsBar', () => {
    it('renders nothing when count is zero', () => {
        // The provider wraps render() in a ToastProvider that always emits a
        // toast-viewport element, so we can't assert on `container.firstChild`
        // — instead verify the bar's region landmark is absent.
        render(<BulkActionsBar count={0} onClear={vi.fn()} onDelete={vi.fn()} />)
        expect(screen.queryByRole('region', { name: /bulk actions/i })).not.toBeInTheDocument()
    })

    it('shows the selected count and Delete + Clear actions when count > 0', () => {
        render(<BulkActionsBar count={4} onClear={vi.fn()} onDelete={vi.fn()} />)
        expect(screen.getByText('4 selected')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /delete 4 selected analyses/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /clear selection/i })).toBeInTheDocument()
    })

    it('renders the Compare link only when compareHref is provided', () => {
        const { rerender } = render(<BulkActionsBar count={1} onClear={vi.fn()} onDelete={vi.fn()} />)
        expect(screen.queryByRole('link', { name: /compare/i })).not.toBeInTheDocument()

        rerender(
            <BulkActionsBar
                count={2}
                onClear={vi.fn()}
                onDelete={vi.fn()}
                compareHref="/analyses/compare?ids=a,b"
            />
        )
        const link = screen.getByRole('link', { name: /compare 2/i })
        expect(link).toBeInTheDocument()
        expect(link.getAttribute('href')).toBe('/analyses/compare?ids=a,b')
    })

    it('fires onDelete when the Delete button is clicked', () => {
        const onDelete = vi.fn()
        render(<BulkActionsBar count={3} onClear={vi.fn()} onDelete={onDelete} />)
        fireEvent.click(screen.getByRole('button', { name: /delete 3/i }))
        expect(onDelete).toHaveBeenCalledTimes(1)
    })

    it('fires onClear when the Clear button is clicked', () => {
        const onClear = vi.fn()
        render(<BulkActionsBar count={3} onClear={onClear} onDelete={vi.fn()} />)
        fireEvent.click(screen.getByRole('button', { name: /clear selection/i }))
        expect(onClear).toHaveBeenCalledTimes(1)
    })

    it('exposes itself as a polite live region so SR announces count changes', () => {
        render(<BulkActionsBar count={2} onClear={vi.fn()} onDelete={vi.fn()} />)
        const region = screen.getByRole('region', { name: /bulk actions/i })
        expect(region.getAttribute('aria-live')).toBe('polite')
    })
})
