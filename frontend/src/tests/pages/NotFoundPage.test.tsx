import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import NotFound from '@/app/not-found'

describe('NotFound (not-found.tsx)', () => {
    it('renders page not found heading', () => {
        render(<NotFound />)
        expect(screen.getByText('Page not found')).toBeInTheDocument()
    })

    it('renders description text', () => {
        render(<NotFound />)
        expect(
            screen.getByText("The page you're looking for doesn't exist or has been moved.")
        ).toBeInTheDocument()
    })

    it('links to dashboard', () => {
        render(<NotFound />)
        const link = screen.getByText('Go to Dashboard')
        expect(link.closest('a')).toHaveAttribute('href', '/dashboard')
    })
})
