import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'
import Badge from '@/components/ui/Badge'
import Card from '@/components/ui/Card'
import Select from '@/components/ui/Select'
import FormField from '@/components/ui/FormField'
import EmptyState from '@/components/ui/EmptyState'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import Skeleton from '@/components/ui/Skeleton'
import ConfirmDialog from '@/components/ui/ConfirmDialog'

describe('Badge', () => {
    it('renders with variant class', () => {
        render(<Badge variant="critical">Critical</Badge>)
        expect(screen.getByText('Critical')).toHaveClass('badge-critical')
    })

    it('defaults to neutral variant', () => {
        render(<Badge>Default</Badge>)
        expect(screen.getByText('Default')).toHaveClass('badge-neutral')
    })
})

describe('Card', () => {
    it('renders children', () => {
        render(<Card>Content</Card>)
        expect(screen.getByText('Content')).toBeInTheDocument()
    })

    it('renders header when provided', () => {
        render(<Card header={<span>Title</span>}>Body</Card>)
        expect(screen.getByText('Title')).toBeInTheDocument()
        expect(screen.getByText('Body')).toBeInTheDocument()
    })

    it('applies card class', () => {
        const { container } = render(<Card>Test</Card>)
        expect(container.firstChild).toHaveClass('card')
    })
})

describe('Select', () => {
    it('renders options', () => {
        render(
            <Select>
                <option value="a">Option A</option>
                <option value="b">Option B</option>
            </Select>
        )
        expect(screen.getByText('Option A')).toBeInTheDocument()
    })

    it('shows error state', () => {
        render(
            <Select error="Pick one" data-testid="select">
                <option>-</option>
            </Select>
        )
        expect(screen.getByText('Pick one')).toBeInTheDocument()
        expect(screen.getByTestId('select')).toHaveClass('input-error')
    })
})

describe('FormField', () => {
    it('renders label and children', () => {
        render(
            <FormField label="Email" htmlFor="email">
                <input id="email" />
            </FormField>
        )
        expect(screen.getByText('Email')).toBeInTheDocument()
    })

    it('shows required indicator', () => {
        render(
            <FormField label="Name" required>
                <input />
            </FormField>
        )
        expect(screen.getByText('*')).toBeInTheDocument()
    })

    it('shows error message', () => {
        render(
            <FormField label="Password" error="Too short">
                <input />
            </FormField>
        )
        expect(screen.getByText('Too short')).toBeInTheDocument()
    })

    it('shows helper text when no error', () => {
        render(
            <FormField label="Bio" helperText="Max 200 chars">
                <textarea />
            </FormField>
        )
        expect(screen.getByText('Max 200 chars')).toBeInTheDocument()
    })
})

describe('EmptyState', () => {
    it('renders title and description', () => {
        render(<EmptyState title="No data" description="Nothing to show" />)
        expect(screen.getByText('No data')).toBeInTheDocument()
        expect(screen.getByText('Nothing to show')).toBeInTheDocument()
    })

    it('renders action', () => {
        render(<EmptyState title="Empty" action={<button>Create</button>} />)
        expect(screen.getByText('Create')).toBeInTheDocument()
    })
})

describe('LoadingSpinner', () => {
    it('renders with status role', () => {
        render(<LoadingSpinner />)
        expect(screen.getByRole('status')).toBeInTheDocument()
    })

    it('renders with aria-label', () => {
        render(<LoadingSpinner />)
        expect(screen.getByLabelText('Loading')).toBeInTheDocument()
    })
})

describe('Skeleton', () => {
    it('renders skeleton element', () => {
        const { container } = render(<Skeleton />)
        expect(container.querySelector('.skeleton')).toBeInTheDocument()
    })

    it('renders multiple skeletons with count', () => {
        const { container } = render(<Skeleton count={3} />)
        expect(container.querySelectorAll('.skeleton')).toHaveLength(3)
    })
})

describe('ConfirmDialog', () => {
    // HTMLDialogElement.showModal is not implemented in jsdom
    // So we test the rendering behavior when open=true

    it('renders nothing when closed', () => {
        const { container } = render(
            <ConfirmDialog
                open={false}
                title="Delete?"
                message="Are you sure?"
                onConfirm={vi.fn()}
                onCancel={vi.fn()}
            />
        )
        expect(container.innerHTML).toBe('')
    })

    it('renders title and message when open', () => {
        render(
            <ConfirmDialog
                open={true}
                title="Delete item?"
                message="This cannot be undone."
                onConfirm={vi.fn()}
                onCancel={vi.fn()}
            />
        )
        expect(screen.getByText('Delete item?')).toBeInTheDocument()
        expect(screen.getByText('This cannot be undone.')).toBeInTheDocument()
    })

    it('calls onConfirm when confirm button clicked', () => {
        const onConfirm = vi.fn()
        render(
            <ConfirmDialog
                open={true}
                title="Delete?"
                message="Sure?"
                confirmLabel="Yes, delete"
                onConfirm={onConfirm}
                onCancel={vi.fn()}
            />
        )
        fireEvent.click(screen.getByText('Yes, delete'))
        expect(onConfirm).toHaveBeenCalledOnce()
    })

    it('calls onCancel when cancel button clicked', () => {
        const onCancel = vi.fn()
        render(
            <ConfirmDialog
                open={true}
                title="Delete?"
                message="Sure?"
                onConfirm={vi.fn()}
                onCancel={onCancel}
            />
        )
        fireEvent.click(screen.getByText('Cancel'))
        expect(onCancel).toHaveBeenCalledOnce()
    })

    it('uses danger variant styling', () => {
        render(
            <ConfirmDialog
                open={true}
                title="Delete?"
                message="Danger!"
                variant="danger"
                confirmLabel="Delete"
                onConfirm={vi.fn()}
                onCancel={vi.fn()}
            />
        )
        expect(screen.getByText('Delete')).toHaveClass('btn-danger')
    })
})
