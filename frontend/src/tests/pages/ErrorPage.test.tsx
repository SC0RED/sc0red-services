import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn() }),
}))

import GlobalError from '@/app/error'

describe('GlobalError (error.tsx)', () => {
    it('renders error message', () => {
        const error = new Error('Test error message')
        render(<GlobalError error={error} reset={vi.fn()} />)

        expect(screen.getByText('Something went wrong')).toBeInTheDocument()
        expect(screen.getByText('Test error message')).toBeInTheDocument()
    })

    it('renders Try again and Dashboard buttons', () => {
        const error = new Error('fail')
        render(<GlobalError error={error} reset={vi.fn()} />)

        expect(screen.getByText('Try again')).toBeInTheDocument()
        expect(screen.getByText('Go to Dashboard')).toBeInTheDocument()
    })

    it('calls reset when Try again is clicked', () => {
        const reset = vi.fn()
        const error = new Error('fail')
        render(<GlobalError error={error} reset={reset} />)

        fireEvent.click(screen.getByText('Try again'))
        expect(reset).toHaveBeenCalledOnce()
    })

    it('links to dashboard', () => {
        const error = new Error('fail')
        render(<GlobalError error={error} reset={vi.fn()} />)

        const link = screen.getByText('Go to Dashboard')
        expect(link.closest('a')).toHaveAttribute('href', '/dashboard')
    })

    it('shows description text', () => {
        const error = new Error('fail')
        render(<GlobalError error={error} reset={vi.fn()} />)

        expect(screen.getByText('An unexpected error occurred while loading this page.')).toBeInTheDocument()
    })
})
