import { render, screen } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'

let mockPathname = '/analyses'

vi.mock('next/navigation', () => ({
    usePathname: () => mockPathname,
}))

import Breadcrumbs from '@/components/ui/Breadcrumbs'

describe('Breadcrumbs', () => {
    it('renders nothing on dashboard', () => {
        mockPathname = '/dashboard'
        const { container } = render(<Breadcrumbs />)
        expect(container.innerHTML).toBe('')
    })

    it('renders breadcrumbs for analyses page', () => {
        mockPathname = '/analyses'
        render(<Breadcrumbs />)
        expect(screen.getByText('Dashboard')).toBeInTheDocument()
        expect(screen.getByText('Analyses')).toBeInTheDocument()
    })

    it('renders breadcrumbs for team page', () => {
        mockPathname = '/team'
        render(<Breadcrumbs />)
        expect(screen.getByText('Dashboard')).toBeInTheDocument()
        expect(screen.getByText('Team')).toBeInTheDocument()
    })

    it('marks last segment as current page', () => {
        mockPathname = '/analyses'
        render(<Breadcrumbs />)
        expect(screen.getByText('Analyses')).toHaveAttribute('aria-current', 'page')
    })

    it('has accessible navigation label', () => {
        mockPathname = '/team'
        render(<Breadcrumbs />)
        expect(screen.getByLabelText('Breadcrumb')).toBeInTheDocument()
    })
})
