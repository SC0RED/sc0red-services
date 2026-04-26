import { screen, fireEvent, waitFor, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

import { renderWithProviders as render } from '@/tests/test-utils'

vi.mock('next-auth/react', () => ({
    useSession: () => ({ data: { user: { id: 'user-1', name: 'Admin', role: 'admin' } } }),
}))

import TeamView from '@/app/(authenticated)/team/TeamView'

const mockMembers = [
    { id: 'user-1', email: 'admin@test.com', name: 'Admin User', role: 'admin' },
    { id: 'user-2', email: 'analyst@test.com', name: 'Analyst User', role: 'analyst' },
]

const mockInvitations = [
    { id: 'inv-1', email: 'pending@test.com', role: 'analyst', status: 'pending', invitedAt: '2026-03-01' },
]

describe('TeamView', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        global.fetch = vi.fn()
    })

    it('renders members list', () => {
        render(<TeamView initialMembers={mockMembers} initialInvitations={[]} />)
        expect(screen.getByText('Admin User')).toBeInTheDocument()
        expect(screen.getByText('Analyst User')).toBeInTheDocument()
        expect(screen.getByText('Members (2)')).toBeInTheDocument()
    })

    it('renders pending invitations', () => {
        render(<TeamView initialMembers={[]} initialInvitations={mockInvitations} />)
        expect(screen.getByText('pending@test.com')).toBeInTheDocument()
        expect(screen.getByText('Pending Invitations (1)')).toBeInTheDocument()
    })

    it('renders invite form', () => {
        render(<TeamView initialMembers={[]} initialInvitations={[]} />)
        expect(screen.getByLabelText('Email')).toBeInTheDocument()
        expect(screen.getByLabelText('Role')).toBeInTheDocument()
        expect(screen.getByText('Send Invite')).toBeInTheDocument()
    })

    it('does not show remove button for self', () => {
        render(<TeamView initialMembers={mockMembers} initialInvitations={[]} />)
        // admin@test.com is user-1 (self) — no remove button
        expect(screen.queryByLabelText('Remove admin@test.com')).not.toBeInTheDocument()
        // analyst@test.com is user-2 — has remove button
        expect(screen.getByLabelText('Remove analyst@test.com')).toBeInTheDocument()
    })

    it('shows role badges', () => {
        render(<TeamView initialMembers={mockMembers} initialInvitations={[]} />)
        expect(screen.getByText('admin')).toBeInTheDocument()
        expect(screen.getByText('analyst')).toBeInTheDocument()
    })

    it('shows resend and revoke buttons for pending invitations', () => {
        render(<TeamView initialMembers={[]} initialInvitations={mockInvitations} />)
        expect(screen.getByText('Resend')).toBeInTheDocument()
        expect(screen.getByLabelText('Revoke invitation for pending@test.com')).toBeInTheDocument()
    })

    describe('invite + resend (toast feedback)', () => {
        it('sends invite on form submit', async () => {
            const mockFetch = vi.fn().mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ invitationId: 'inv-new', email: 'new@test.com' }),
            })
            global.fetch = mockFetch

            render(<TeamView initialMembers={[]} initialInvitations={[]} />)

            fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'new@test.com' } })
            fireEvent.click(screen.getByText('Send Invite'))

            await waitFor(() => {
                expect(mockFetch).toHaveBeenCalledWith(
                    '/api/org/invite',
                    expect.objectContaining({
                        method: 'POST',
                    })
                )
            })

            // Success toast surfaces (replaces the old inline alert div)
            await waitFor(() => {
                expect(screen.getByText('Invitation sent to new@test.com')).toBeInTheDocument()
            })
        })

        it('surfaces server error via toast on failed invite', async () => {
            global.fetch = vi.fn().mockResolvedValue({
                ok: false,
                json: () => Promise.resolve({ error: 'Email already exists' }),
            })

            render(<TeamView initialMembers={[]} initialInvitations={[]} />)

            fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'dup@test.com' } })
            fireEvent.click(screen.getByText('Send Invite'))

            await waitFor(() => {
                // The error appears in a toast (role="alert"), not an inline div
                expect(screen.getByText('Email already exists')).toBeInTheDocument()
            })
        })
    })

    describe('revoke invitation (toast.undo)', () => {
        beforeEach(() => {
            vi.useFakeTimers()
        })

        afterEach(() => {
            vi.useRealTimers()
        })

        it('optimistically removes the row immediately and shows Undo toast', () => {
            render(<TeamView initialMembers={[]} initialInvitations={mockInvitations} />)

            fireEvent.click(screen.getByLabelText('Revoke invitation for pending@test.com'))

            // Row removed immediately
            expect(screen.queryByText('pending@test.com')).not.toBeInTheDocument()
            // Toast with Undo appears
            expect(screen.getByText('Revoked invitation for pending@test.com')).toBeInTheDocument()
            expect(screen.getByText('Undo')).toBeInTheDocument()
        })

        it('does NOT call DELETE before the 5s window expires', () => {
            global.fetch = vi.fn().mockResolvedValue({ ok: true })
            render(<TeamView initialMembers={[]} initialInvitations={mockInvitations} />)
            fireEvent.click(screen.getByLabelText('Revoke invitation for pending@test.com'))

            act(() => {
                vi.advanceTimersByTime(4999)
            })
            expect(global.fetch).not.toHaveBeenCalled()
        })

        it('calls DELETE after the 5s window expires', async () => {
            global.fetch = vi.fn().mockResolvedValue({ ok: true })
            render(<TeamView initialMembers={[]} initialInvitations={mockInvitations} />)
            fireEvent.click(screen.getByLabelText('Revoke invitation for pending@test.com'))

            await act(async () => {
                await vi.advanceTimersByTimeAsync(5000)
            })

            expect(global.fetch).toHaveBeenCalledWith('/api/org/invite/inv-1', { method: 'DELETE' })
        })

        it('clicking Undo restores the row and skips DELETE', () => {
            global.fetch = vi.fn().mockResolvedValue({ ok: true })
            render(<TeamView initialMembers={[]} initialInvitations={mockInvitations} />)
            fireEvent.click(screen.getByLabelText('Revoke invitation for pending@test.com'))
            // Row gone after click
            expect(screen.queryByText('pending@test.com')).not.toBeInTheDocument()

            fireEvent.click(screen.getByText('Undo'))

            // Row is back
            expect(screen.getByText('pending@test.com')).toBeInTheDocument()
            // No DELETE fires even after timer expiry
            act(() => {
                vi.advanceTimersByTime(10_000)
            })
            expect(global.fetch).not.toHaveBeenCalled()
        })

        it('restores the row on DELETE failure', async () => {
            global.fetch = vi.fn().mockResolvedValue({ ok: false })
            render(<TeamView initialMembers={[]} initialInvitations={mockInvitations} />)
            fireEvent.click(screen.getByLabelText('Revoke invitation for pending@test.com'))
            expect(screen.queryByText('pending@test.com')).not.toBeInTheDocument()

            await act(async () => {
                await vi.advanceTimersByTimeAsync(5000)
            })

            // Row restored, error toast surfaced
            expect(screen.getByText('pending@test.com')).toBeInTheDocument()
            expect(screen.getByText('Failed to revoke invitation')).toBeInTheDocument()
        })
    })

    describe('remove member (toast.undo)', () => {
        beforeEach(() => {
            vi.useFakeTimers()
        })

        afterEach(() => {
            vi.useRealTimers()
        })

        it('optimistically removes the row and shows Undo toast', () => {
            render(<TeamView initialMembers={mockMembers} initialInvitations={[]} />)

            fireEvent.click(screen.getByLabelText('Remove analyst@test.com'))

            expect(screen.queryByText('Analyst User')).not.toBeInTheDocument()
            expect(screen.getByText('Removed analyst@test.com from the team')).toBeInTheDocument()
            expect(screen.getByText('Undo')).toBeInTheDocument()
        })

        it('calls DELETE after the 5s window expires', async () => {
            global.fetch = vi.fn().mockResolvedValue({ ok: true })
            render(<TeamView initialMembers={mockMembers} initialInvitations={[]} />)
            fireEvent.click(screen.getByLabelText('Remove analyst@test.com'))

            await act(async () => {
                await vi.advanceTimersByTimeAsync(5000)
            })

            expect(global.fetch).toHaveBeenCalledWith('/api/org/members/user-2', { method: 'DELETE' })
        })

        it('clicking Undo restores the member and skips DELETE', () => {
            global.fetch = vi.fn().mockResolvedValue({ ok: true })
            render(<TeamView initialMembers={mockMembers} initialInvitations={[]} />)
            fireEvent.click(screen.getByLabelText('Remove analyst@test.com'))
            expect(screen.queryByText('Analyst User')).not.toBeInTheDocument()

            fireEvent.click(screen.getByText('Undo'))

            expect(screen.getByText('Analyst User')).toBeInTheDocument()
            act(() => {
                vi.advanceTimersByTime(10_000)
            })
            expect(global.fetch).not.toHaveBeenCalled()
        })
    })

    it('shows empty state when no members', () => {
        render(<TeamView initialMembers={[]} initialInvitations={[]} />)
        expect(screen.getByText('No members yet.')).toBeInTheDocument()
    })
})
