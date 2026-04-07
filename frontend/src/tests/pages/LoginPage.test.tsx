import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

import LoginPage from '@/app/login/page'

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

describe('LoginPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockStatus = 'unauthenticated'
    })

    it('renders login form when unauthenticated', () => {
        render(<LoginPage />)
        expect(screen.getByLabelText('Email')).toBeInTheDocument()
        expect(screen.getByLabelText('Password')).toBeInTheDocument()
        expect(screen.getByText('Sign In')).toBeInTheDocument()
    })

    it('always renders form even with active session (middleware handles auth redirect)', () => {
        mockStatus = 'authenticated'
        render(<LoginPage />)
        expect(screen.getByLabelText('Email')).toBeInTheDocument()
        expect(screen.getByText('Sign In')).toBeInTheDocument()
    })

    it('shows error on invalid credentials', async () => {
        mockSignIn.mockResolvedValue({ ok: false })
        render(<LoginPage />)

        fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'test@test.com' } })
        fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrong' } })
        fireEvent.click(screen.getByText('Sign In'))

        await waitFor(() => {
            expect(screen.getByText('Invalid email or password')).toBeInTheDocument()
        })
    })

    it('redirects to dashboard on successful login', async () => {
        mockSignIn.mockResolvedValue({ ok: true })
        render(<LoginPage />)

        fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'test@test.com' } })
        fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'correct' } })
        fireEvent.click(screen.getByText('Sign In'))

        await waitFor(() => {
            expect(mockPush).toHaveBeenCalledWith('/dashboard')
        })
    })

    it('has link to signup page', () => {
        render(<LoginPage />)
        expect(screen.getByText('Create one')).toBeInTheDocument()
    })
})
