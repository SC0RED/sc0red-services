import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

import SignupPage from '@/app/signup/page'

const mockReplace = vi.fn()
const mockPush = vi.fn()
const mockSignIn = vi.fn()
let mockStatus = 'unauthenticated'

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        replace: mockReplace,
        push: mockPush,
    }),
}))

vi.mock('next-auth/react', () => ({
    useSession: () => ({ status: mockStatus }),
    signIn: (...args: unknown[]) => mockSignIn(...args),
}))

global.fetch = vi.fn()

describe('SignupPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockStatus = 'unauthenticated'
    })

    it('renders signup form when unauthenticated', () => {
        render(<SignupPage />)
        expect(screen.getByLabelText('Work email')).toBeInTheDocument()
        expect(screen.getByLabelText('Password')).toBeInTheDocument()
        expect(screen.getByLabelText('Firm name')).toBeInTheDocument()
        expect(screen.getByText('Create Account & Start')).toBeInTheDocument()
    })

    it('redirects to dashboard when already authenticated', () => {
        mockStatus = 'authenticated'
        const { container } = render(<SignupPage />)
        expect(mockReplace).toHaveBeenCalledWith('/dashboard')
        expect(container.innerHTML).toBe('')
    })

    it('shows error when registration fails', async () => {
        ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
            ok: false,
            json: () => Promise.resolve({ error: 'Email already registered' }),
        })

        render(<SignupPage />)

        fireEvent.change(screen.getByLabelText('Your name'), { target: { value: 'Test User' } })
        fireEvent.change(screen.getByLabelText('Work email'), { target: { value: 'test@test.com' } })
        fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } })
        fireEvent.change(screen.getByLabelText('Firm name'), { target: { value: 'Test Org' } })
        fireEvent.click(screen.getByText('Create Account & Start'))

        await waitFor(() => {
            expect(screen.getByText('Email already registered')).toBeInTheDocument()
        })
    })

    it('signs in and redirects after successful registration', async () => {
        ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ success: true }),
        })
        mockSignIn.mockResolvedValue({ ok: true })

        render(<SignupPage />)

        fireEvent.change(screen.getByLabelText('Your name'), { target: { value: 'Test User' } })
        fireEvent.change(screen.getByLabelText('Work email'), { target: { value: 'test@test.com' } })
        fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } })
        fireEvent.change(screen.getByLabelText('Firm name'), { target: { value: 'Test Org' } })
        fireEvent.click(screen.getByText('Create Account & Start'))

        await waitFor(() => {
            expect(mockSignIn).toHaveBeenCalledWith('credentials', {
                email: 'test@test.com',
                password: 'password123',
                redirect: false,
            })
            expect(mockPush).toHaveBeenCalledWith('/dashboard')
        })
    })

    it('has link to login page', () => {
        render(<SignupPage />)
        expect(screen.getByText('Sign in')).toBeInTheDocument()
    })
})
