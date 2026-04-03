import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn() }),
    useSearchParams: () => ({
        get: (key: string) => (key === 'email' ? 'invited@test.com' : null),
    }),
}))

vi.mock('@/lib/auth/cognitoClient', () => ({
    signInWithCognito: vi.fn(),
    completeNewPasswordChallenge: vi.fn(),
}))

import AcceptInvitePage from '@/app/accept-invite/page'
import { signInWithCognito, completeNewPasswordChallenge } from '@/lib/auth/cognitoClient'

describe('AcceptInvitePage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('renders with email from URL params', () => {
        render(<AcceptInvitePage />)
        expect(screen.getByText('Accept Invitation')).toBeInTheDocument()
        expect(screen.getByDisplayValue('invited@test.com')).toBeInTheDocument()
    })

    it('renders temp password and new password fields', () => {
        render(<AcceptInvitePage />)
        expect(screen.getByLabelText('Temporary Password')).toBeInTheDocument()
        expect(screen.getByLabelText('New Password')).toBeInTheDocument()
        expect(screen.getByText('Set Password & Join')).toBeInTheDocument()
    })

    it('completes password challenge and shows success', async () => {
        const mockCognitoUser = {}
        vi.mocked(signInWithCognito).mockResolvedValue({
            idToken: '',
            accessToken: '',
            refreshToken: '',
            challengeName: 'NEW_PASSWORD_REQUIRED',
            cognitoUser: mockCognitoUser as never,
        })
        vi.mocked(completeNewPasswordChallenge).mockResolvedValue({
            idToken: 'token',
            accessToken: 'access',
            refreshToken: 'refresh',
        })

        render(<AcceptInvitePage />)

        fireEvent.change(screen.getByLabelText('Temporary Password'), { target: { value: 'TempPass1!' } })
        fireEvent.change(screen.getByLabelText('New Password'), { target: { value: 'NewPass123' } })
        fireEvent.click(screen.getByText('Set Password & Join'))

        await waitFor(() => {
            expect(signInWithCognito).toHaveBeenCalledWith('invited@test.com', 'TempPass1!')
            expect(completeNewPasswordChallenge).toHaveBeenCalledWith(mockCognitoUser, 'NewPass123')
            expect(screen.getByText('Your password has been set. You can now log in.')).toBeInTheDocument()
        })
    })

    it('shows success if user already has permanent password', async () => {
        vi.mocked(signInWithCognito).mockResolvedValue({
            idToken: 'token',
            accessToken: 'access',
            refreshToken: 'refresh',
        })

        render(<AcceptInvitePage />)

        fireEvent.change(screen.getByLabelText('Temporary Password'), { target: { value: 'Pass1234' } })
        fireEvent.change(screen.getByLabelText('New Password'), { target: { value: 'NewPass123' } })
        fireEvent.click(screen.getByText('Set Password & Join'))

        await waitFor(() => {
            expect(screen.getByText('Your password has been set. You can now log in.')).toBeInTheDocument()
            expect(completeNewPasswordChallenge).not.toHaveBeenCalled()
        })
    })

    it('shows error on authentication failure', async () => {
        vi.mocked(signInWithCognito).mockRejectedValue(new Error('Incorrect password'))

        render(<AcceptInvitePage />)

        fireEvent.change(screen.getByLabelText('Temporary Password'), { target: { value: 'wrong' } })
        fireEvent.change(screen.getByLabelText('New Password'), { target: { value: 'NewPass123' } })
        fireEvent.click(screen.getByText('Set Password & Join'))

        await waitFor(() => {
            expect(screen.getByText('Incorrect password')).toBeInTheDocument()
        })
    })

    it('has go to login link on success', async () => {
        vi.mocked(signInWithCognito).mockResolvedValue({
            idToken: 'token',
            accessToken: 'access',
            refreshToken: 'refresh',
        })

        render(<AcceptInvitePage />)

        fireEvent.change(screen.getByLabelText('Temporary Password'), { target: { value: 'Pass1234' } })
        fireEvent.change(screen.getByLabelText('New Password'), { target: { value: 'NewPass123' } })
        fireEvent.click(screen.getByText('Set Password & Join'))

        await waitFor(() => {
            expect(screen.getByText('Go to Login')).toBeInTheDocument()
        })
    })
})
