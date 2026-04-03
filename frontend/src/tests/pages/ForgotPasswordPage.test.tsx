import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

vi.mock('@/lib/auth/cognitoClient', () => ({
    forgotPassword: vi.fn(),
    confirmForgotPassword: vi.fn(),
}))

import ForgotPasswordPage from '@/app/forgot-password/page'
import { forgotPassword, confirmForgotPassword } from '@/lib/auth/cognitoClient'

describe('ForgotPasswordPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('renders email input on initial step', () => {
        render(<ForgotPasswordPage />)
        expect(screen.getByText('Reset Password')).toBeInTheDocument()
        expect(screen.getByLabelText('Email')).toBeInTheDocument()
        expect(screen.getByText('Send Reset Code')).toBeInTheDocument()
    })

    it('calls forgotPassword and advances to code step', async () => {
        vi.mocked(forgotPassword).mockResolvedValue()

        render(<ForgotPasswordPage />)

        fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@test.com' } })
        fireEvent.click(screen.getByText('Send Reset Code'))

        await waitFor(() => {
            expect(forgotPassword).toHaveBeenCalledWith('user@test.com')
            expect(screen.getByLabelText('Verification Code')).toBeInTheDocument()
            expect(screen.getByLabelText('New Password')).toBeInTheDocument()
        })
    })

    it('shows error when forgotPassword fails', async () => {
        vi.mocked(forgotPassword).mockRejectedValue(new Error('User not found'))

        render(<ForgotPasswordPage />)

        fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'bad@test.com' } })
        fireEvent.click(screen.getByText('Send Reset Code'))

        await waitFor(() => {
            expect(screen.getByText('User not found')).toBeInTheDocument()
        })
    })

    it('confirms password reset and shows success', async () => {
        vi.mocked(forgotPassword).mockResolvedValue()
        vi.mocked(confirmForgotPassword).mockResolvedValue()

        render(<ForgotPasswordPage />)

        // Step 1: enter email
        fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@test.com' } })
        fireEvent.click(screen.getByText('Send Reset Code'))

        await waitFor(() => {
            expect(screen.getByLabelText('Verification Code')).toBeInTheDocument()
        })

        // Step 2: enter code and new password
        fireEvent.change(screen.getByLabelText('Verification Code'), { target: { value: '123456' } })
        fireEvent.change(screen.getByLabelText('New Password'), { target: { value: 'NewPass123' } })
        fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }))

        await waitFor(() => {
            expect(confirmForgotPassword).toHaveBeenCalledWith('user@test.com', '123456', 'NewPass123')
            expect(screen.getByText('Your password has been reset successfully.')).toBeInTheDocument()
        })
    })

    it('shows error when confirmForgotPassword fails', async () => {
        vi.mocked(forgotPassword).mockResolvedValue()
        vi.mocked(confirmForgotPassword).mockRejectedValue(new Error('Invalid code'))

        render(<ForgotPasswordPage />)

        fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@test.com' } })
        fireEvent.click(screen.getByText('Send Reset Code'))

        await waitFor(() => {
            expect(screen.getByLabelText('Verification Code')).toBeInTheDocument()
        })

        fireEvent.change(screen.getByLabelText('Verification Code'), { target: { value: 'wrong' } })
        fireEvent.change(screen.getByLabelText('New Password'), { target: { value: 'NewPass123' } })
        fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }))

        await waitFor(() => {
            expect(screen.getByText('Invalid code')).toBeInTheDocument()
        })
    })

    it('has back to login link', () => {
        render(<ForgotPasswordPage />)
        expect(screen.getByText('Back to Login')).toBeInTheDocument()
    })
})
