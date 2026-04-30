import { screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

import { renderWithProviders as render } from '@/tests/test-utils'

const mockSignOut = vi.fn()
let mockSession: { user?: Record<string, unknown> | null } = {
    user: {
        name: 'Alice Admin',
        email: 'alice@test.com',
        orgId: 'org-abc-123',
        role: 'admin',
    },
}

vi.mock('next-auth/react', () => ({
    useSession: () => ({ data: mockSession }),
    signOut: (opts: unknown) => mockSignOut(opts),
}))

import SettingsView from '@/app/(authenticated)/settings/SettingsView'

describe('SettingsView', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockSession = {
            user: {
                name: 'Alice Admin',
                email: 'alice@test.com',
                orgId: 'org-abc-123',
                role: 'admin',
            },
        }
    })

    describe('Profile section', () => {
        it('renders user name and email read-only from session', () => {
            render(<SettingsView />)
            expect(screen.getByText('Alice Admin')).toBeInTheDocument()
            expect(screen.getByText('alice@test.com')).toBeInTheDocument()
        })

        it('renders dash placeholders when fields are missing', () => {
            mockSession = { user: { name: '', email: '', orgId: '', role: '' } }
            render(<SettingsView />)
            const dashes = screen.getAllByText('—')
            // Name + Email + Organisation ID
            expect(dashes.length).toBeGreaterThanOrEqual(3)
        })
    })

    describe('Organisation section', () => {
        it('renders orgId in monospaced text', () => {
            const { container } = render(<SettingsView />)
            expect(screen.getByText('org-abc-123')).toBeInTheDocument()
            // The value sits next to a Copy button — pin both render together
            expect(container.querySelector('button[aria-label="Copy organisation ID"]')).not.toBeNull()
        })

        it('renders role as a badge', () => {
            const { container } = render(<SettingsView />)
            const badge = container.querySelector('.badge')
            expect(badge).not.toBeNull()
            expect(badge?.textContent).toBe('admin')
        })

        it('falls back to "member" role when session role is empty', () => {
            mockSession = {
                user: {
                    name: 'Bob',
                    email: 'bob@test.com',
                    orgId: 'org-1',
                    role: '',
                },
            }
            const { container } = render(<SettingsView />)
            const badge = container.querySelector('.badge')
            expect(badge?.textContent).toBe('member')
        })

        it('does not render the Copy button when orgId is empty', () => {
            mockSession = { user: { name: 'X', email: 'x@x.com', orgId: '', role: 'admin' } }
            const { container } = render(<SettingsView />)
            expect(container.querySelector('button[aria-label="Copy organisation ID"]')).toBeNull()
        })

        it('copies orgId to clipboard and shows success toast', async () => {
            const writeText = vi.fn().mockResolvedValue(undefined)
            Object.assign(navigator, { clipboard: { writeText } })

            render(<SettingsView />)
            fireEvent.click(screen.getByLabelText('Copy organisation ID'))

            await waitFor(() => {
                expect(writeText).toHaveBeenCalledWith('org-abc-123')
            })
            // Toast surfaces
            await waitFor(() => {
                expect(screen.getByText('Copied org ID')).toBeInTheDocument()
            })
            // Button text flips to "Copied" briefly
            await waitFor(() => {
                expect(screen.getByLabelText('Copy organisation ID').textContent).toBe('Copied')
            })
        })

        it('surfaces error toast when clipboard write fails', async () => {
            const writeText = vi.fn().mockRejectedValue(new Error('denied'))
            Object.assign(navigator, { clipboard: { writeText } })

            render(<SettingsView />)
            fireEvent.click(screen.getByLabelText('Copy organisation ID'))

            await waitFor(() => {
                expect(screen.getByText('Failed to copy. Select the value manually.')).toBeInTheDocument()
            })
        })
    })

    describe('Sign out', () => {
        it('renders a Sign out button', () => {
            render(<SettingsView />)
            expect(screen.getByText('Sign out')).toBeInTheDocument()
        })

        it('calls signOut with /login callback when clicked', () => {
            render(<SettingsView />)
            fireEvent.click(screen.getByText('Sign out'))
            expect(mockSignOut).toHaveBeenCalledWith({ callbackUrl: '/login' })
        })
    })

    describe('Appearance section', () => {
        it('renders the Appearance section with the theme toggle', () => {
            render(<SettingsView />)
            expect(screen.getByText('Appearance')).toBeInTheDocument()
            const group = screen.getByRole('radiogroup', { name: 'Theme preference' })
            expect(group).toBeInTheDocument()
            // Three options
            const radios = group.querySelectorAll('input[type="radio"]')
            expect(radios).toHaveLength(3)
        })
    })
})
