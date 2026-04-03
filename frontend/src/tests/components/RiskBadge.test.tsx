import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import RiskBadge from '@/components/RiskBadge'

describe('RiskBadge', () => {
    it('renders "Low Risk" for low tier', () => {
        render(<RiskBadge tier="low" />)
        expect(screen.getByText('Low Risk')).toBeInTheDocument()
    })

    it('renders "Moderate Risk" for moderate tier', () => {
        render(<RiskBadge tier="moderate" />)
        expect(screen.getByText('Moderate Risk')).toBeInTheDocument()
    })

    it('renders "High Risk" for high tier', () => {
        render(<RiskBadge tier="high" />)
        expect(screen.getByText('High Risk')).toBeInTheDocument()
    })

    it('renders "Critical Risk" for critical tier', () => {
        render(<RiskBadge tier="critical" />)
        expect(screen.getByText('Critical Risk')).toBeInTheDocument()
    })

    it('applies the correct badge CSS class for the tier', () => {
        const { container } = render(<RiskBadge tier="low" />)
        expect(container.firstChild).toHaveClass('badge-low')
    })

    it('applies the base badge CSS class', () => {
        const { container } = render(<RiskBadge tier="high" />)
        expect(container.firstChild).toHaveClass('badge')
    })

    it('renders a dot indicator element', () => {
        const { container } = render(<RiskBadge tier="moderate" />)
        const dot = container.querySelector('span > span')
        expect(dot).toBeInTheDocument()
    })
})
