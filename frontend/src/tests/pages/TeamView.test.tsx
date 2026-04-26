import { screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

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
    })

    it('shows error on failed invite', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            ok: false,
            json: () => Promise.resolve({ error: 'Email already exists' }),
        })

        render(<TeamView initialMembers={[]} initialInvitations={[]} />)

        fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'dup@test.com' } })
        fireEvent.click(screen.getByText('Send Invite'))

        await waitFor(() => {
            expect(screen.getByText('Email already exists')).toBeInTheDocument()
        })
    })

    it('removes member on delete', async () => {
        global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) })
        window.confirm = vi.fn().mockReturnValue(true)

        render(<TeamView initialMembers={mockMembers} initialInvitations={[]} />)

        fireEvent.click(screen.getByLabelText('Remove analyst@test.com'))

        await waitFor(() => {
            expect(screen.queryByText('Analyst User')).not.toBeInTheDocument()
        })
    })

    it('shows empty state when no members', () => {
        render(<TeamView initialMembers={[]} initialInvitations={[]} />)
        expect(screen.getByText('No members yet.')).toBeInTheDocument()
    })
})
