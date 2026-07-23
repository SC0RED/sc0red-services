import { fireEvent, screen, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

import { renderWithProviders } from '@/tests/test-utils'

// GlobalShortcuts (renders the modals) + SidebarFooter (the clickable affordance)
// must share one ShortcutsUiProvider — renderWithProviders supplies it, so
// rendering both together exercises the click-opens-modal wiring end to end.
const mockPush = vi.fn()
vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: mockPush, refresh: vi.fn() }),
    usePathname: () => '/dashboard',
}))
vi.mock('next-auth/react', () => ({
    useSession: () => ({ data: { user: { name: 'Test User', email: 'test@example.com' } } }),
    signOut: vi.fn(),
}))

import GlobalShortcuts from '@/components/GlobalShortcuts'
import SidebarFooter from '@/components/sidebar/SidebarFooter'

function renderBoth() {
    return renderWithProviders(
        <>
            <SidebarFooter />
            <GlobalShortcuts />
        </>
    )
}

describe('discoverability affordance', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ analyses: [], recentScans: [] }),
        })
    })

    it('clicking "commands" in the footer opens the command palette', async () => {
        renderBoth()
        expect(screen.queryByPlaceholderText(/Search companies/)).not.toBeInTheDocument()
        fireEvent.click(screen.getByLabelText('Open command palette'))
        await waitFor(() => expect(screen.getByPlaceholderText(/Search companies/)).toBeInTheDocument())
    })

    it('clicking "shortcuts" in the footer opens the keyboard-shortcuts help', async () => {
        renderBoth()
        fireEvent.click(screen.getByLabelText('Show keyboard shortcuts'))
        // A listed nav chord only appears inside the shortcuts help modal.
        await waitFor(() => expect(screen.getByText('Go to Dashboard')).toBeInTheDocument())
    })

    it('the command palette exposes a "Keyboard shortcuts" action that opens the help', async () => {
        renderBoth()
        fireEvent.click(screen.getByLabelText('Open command palette'))
        await waitFor(() => screen.getByPlaceholderText(/Search companies/))
        fireEvent.click(screen.getByText('Keyboard shortcuts'))
        await waitFor(() => expect(screen.getByText('Go to Dashboard')).toBeInTheDocument())
    })
})
