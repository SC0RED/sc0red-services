import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

const mockSignOut = vi.fn()

vi.mock('next-auth/react', () => ({
    useSession: () => ({
        data: { user: { name: 'Test User', email: 'test@example.com' } },
    }),
    signOut: (...args: unknown[]) => mockSignOut(...args),
}))

vi.mock('next/navigation', () => ({
    usePathname: () => '/dashboard',
}))

import DashboardSidebar from '@/components/DashboardSidebar'

describe('DashboardSidebar', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('renders navigation links', () => {
        render(<DashboardSidebar />)

        expect(screen.getByText('Dashboard')).toBeInTheDocument()
        expect(screen.getAllByText('New Scan').length).toBeGreaterThanOrEqual(1)
        expect(screen.getByText('Analyses')).toBeInTheDocument()
    })

    it('links have correct href values', () => {
        render(<DashboardSidebar />)

        const dashboardLink = screen.getByText('Dashboard').closest('a')
        expect(dashboardLink).toHaveAttribute('href', '/dashboard')

        const analysesLink = screen.getByText('Analyses').closest('a')
        expect(analysesLink).toHaveAttribute('href', '/analyses')

        // "New Scan" appears as both a nav link and a button-style link
        const newScanLinks = screen.getAllByText('New Scan')
        const navNewScan = newScanLinks[0].closest('a')
        expect(navNewScan).toHaveAttribute('href', '/scan/new')
    })

    it('sign out button is present and calls signOut', () => {
        render(<DashboardSidebar />)

        const signOutButton = screen.getByTitle('Sign out')
        expect(signOutButton).toBeInTheDocument()

        fireEvent.click(signOutButton)
        expect(mockSignOut).toHaveBeenCalledWith({ callbackUrl: '/login' })
    })

    it('renders user name and email', () => {
        render(<DashboardSidebar />)

        expect(screen.getByText('Test User')).toBeInTheDocument()
        expect(screen.getByText('test@example.com')).toBeInTheDocument()
    })

    it('renders user initial avatar', () => {
        render(<DashboardSidebar />)

        expect(screen.getByText('T')).toBeInTheDocument()
    })

    it('renders Janus branding', () => {
        render(<DashboardSidebar />)

        expect(screen.getByText('Janus')).toBeInTheDocument()
        expect(screen.getByText('AI Intelligence')).toBeInTheDocument()
    })
})
