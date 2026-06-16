import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

import SignupPage from '@/app/signup/page'

const mockReplace = vi.fn()
const mockPush = vi.fn()
const mockSignIn = vi.fn()
let mockStatus = 'unauthenticated'
let mockCallbackUrl: string | null = null

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        replace: mockReplace,
        push: mockPush,
    }),
    useSearchParams: () => ({
        get: (key: string) => (key === 'callbackUrl' ? mockCallbackUrl : null),
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
        mockCallbackUrl = null
    })

    it('renders signup form when unauthenticated', () => {
        render(<SignupPage />)
        expect(screen.getByLabelText('Work email')).toBeInTheDocument()
        expect(screen.getByLabelText('Password')).toBeInTheDocument()
        expect(screen.getByLabelText('Firm name')).toBeInTheDocument()
        expect(screen.getByText('Create Account & Start')).toBeInTheDocument()
    })

    it('always renders form even with active session (middleware handles auth redirect)', () => {
        mockStatus = 'authenticated'
        render(<SignupPage />)
        expect(screen.getByLabelText('Work email')).toBeInTheDocument()
        expect(screen.getByText('Create Account & Start')).toBeInTheDocument()
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

    it('returns to the callbackUrl after signup (new user in OAuth consent flow)', async () => {
        mockCallbackUrl = '/oauth/authorize?client_id=abc&scope=read+write&state=xyz'
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
            expect(mockPush).toHaveBeenCalledWith('/oauth/authorize?client_id=abc&scope=read+write&state=xyz')
        })
    })

    it('has link to login page', () => {
        render(<SignupPage />)
        expect(screen.getByText('Sign in')).toBeInTheDocument()
    })
})
