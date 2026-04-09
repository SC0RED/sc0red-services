import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'
import Button from '@/components/ui/Button'

describe('Button', () => {
    it('renders children', () => {
        render(<Button>Click me</Button>)
        expect(screen.getByText('Click me')).toBeInTheDocument()
    })

    it('applies variant class', () => {
        render(<Button variant="danger">Delete</Button>)
        expect(screen.getByText('Delete')).toHaveClass('btn-danger')
    })

    it('applies size class', () => {
        render(<Button size="sm">Small</Button>)
        expect(screen.getByText('Small')).toHaveClass('btn-sm')
    })

    it('shows loading state', () => {
        render(<Button loading>Save</Button>)
        const button = screen.getByRole('button')
        expect(button).toBeDisabled()
        expect(screen.getByText('Save')).toBeInTheDocument()
    })

    it('renders icon', () => {
        render(<Button icon={<span data-testid="icon">+</span>}>Add</Button>)
        expect(screen.getByTestId('icon')).toBeInTheDocument()
    })

    it('calls onClick', () => {
        const onClick = vi.fn()
        render(<Button onClick={onClick}>Click</Button>)
        fireEvent.click(screen.getByText('Click'))
        expect(onClick).toHaveBeenCalledOnce()
    })

    it('is disabled when disabled prop is true', () => {
        render(<Button disabled>Disabled</Button>)
        expect(screen.getByRole('button')).toBeDisabled()
    })
})
