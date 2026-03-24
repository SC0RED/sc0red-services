import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import TopActionsCallout from '@/components/analysis/TopActionsCallout'

describe('TopActionsCallout', () => {
    it('renders all actions with numbered badges', () => {
        const actions = ['Action One', 'Action Two', 'Action Three']
        render(<TopActionsCallout actions={actions} />)

        expect(screen.getByText('Top 3 Immediate Actions')).toBeInTheDocument()
        expect(screen.getByText('Action One')).toBeInTheDocument()
        expect(screen.getByText('Action Two')).toBeInTheDocument()
        expect(screen.getByText('Action Three')).toBeInTheDocument()
        expect(screen.getByText('1')).toBeInTheDocument()
        expect(screen.getByText('2')).toBeInTheDocument()
        expect(screen.getByText('3')).toBeInTheDocument()
    })

    it('renders nothing when actions array is empty', () => {
        const { container } = render(<TopActionsCallout actions={[]} />)
        expect(container.firstChild).toBeNull()
    })

    it('renders single action', () => {
        render(<TopActionsCallout actions={['Only action']} />)
        expect(screen.getByText('Only action')).toBeInTheDocument()
        expect(screen.getByText('1')).toBeInTheDocument()
    })
})
