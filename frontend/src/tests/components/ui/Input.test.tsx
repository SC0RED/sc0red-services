import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import Input from '@/components/ui/Input'

describe('Input', () => {
    it('renders an input element', () => {
        render(<Input placeholder="Enter text" />)
        expect(screen.getByPlaceholderText('Enter text')).toBeInTheDocument()
    })

    it('shows error message', () => {
        render(<Input error="Required field" />)
        expect(screen.getByText('Required field')).toBeInTheDocument()
    })

    it('adds error class when error is present', () => {
        render(<Input error="Invalid" data-testid="input" />)
        expect(screen.getByTestId('input')).toHaveClass('input-error')
    })

    it('sets aria-invalid when error is present', () => {
        render(<Input error="Bad value" data-testid="input" />)
        expect(screen.getByTestId('input')).toHaveAttribute('aria-invalid', 'true')
    })

    it('does not show error class when no error', () => {
        render(<Input data-testid="input" />)
        expect(screen.getByTestId('input')).not.toHaveClass('input-error')
    })
})
