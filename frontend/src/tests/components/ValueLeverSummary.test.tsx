import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'

import ValueLeverSummary from '@/components/ValueLeverSummary'
import type { Opportunity } from '@/lib/types/api'

const mockOpportunities: Opportunity[] = [
    {
        title: 'Deploy AI Chatbot',
        description: 'Build a chatbot',
        impact_rating: 'High',
        timeline: 'Quick Win (1-3 months)',
        strategic_category: 'Competitive Moat',
        value_lever: 'Revenue Side',
    },
    {
        title: 'Automate Support',
        description: 'Reduce support costs',
        impact_rating: 'Medium',
        timeline: 'Medium-term (3-9 months)',
        strategic_category: 'Operational Efficiency',
        value_lever: 'Cost Side',
    },
    {
        title: 'AI Platform',
        description: 'Build platform',
        impact_rating: 'High',
        timeline: 'Long-term (9-18 months)',
        strategic_category: 'Revenue Capture',
        value_lever: 'Both',
    },
    {
        title: 'Second Revenue',
        description: 'Another revenue opportunity',
        impact_rating: 'Medium',
        timeline: 'Quick Win (1-3 months)',
        strategic_category: 'Competitive Moat',
        value_lever: 'Revenue Side',
    },
]

describe('ValueLeverSummary', () => {
    it('returns null when no opportunities have value_lever', () => {
        const noLeverOpps: Opportunity[] = [
            {
                title: 'Old Opportunity',
                description: 'From before value lever',
                impact_rating: 'High',
                timeline: 'Quick Win (1-3 months)',
                strategic_category: 'Competitive Moat',
                implementation_steps: ['Step 1'],
            },
        ]
        const onLeverChange = vi.fn()
        const { container } = render(
            <ValueLeverSummary opportunities={noLeverOpps} activeLever="All" onLeverChange={onLeverChange} />
        )
        expect(container.innerHTML).toBe('')
    })

    it('shows 3 lever cards with correct counts', () => {
        const onLeverChange = vi.fn()
        render(
            <ValueLeverSummary
                opportunities={mockOpportunities}
                activeLever="All"
                onLeverChange={onLeverChange}
            />
        )

        expect(screen.getByText('Value Impact')).toBeInTheDocument()
        expect(screen.getByText('Revenue Side')).toBeInTheDocument()
        expect(screen.getByText('Cost Side')).toBeInTheDocument()
        expect(screen.getByText('Both')).toBeInTheDocument()

        // Revenue Side has 2, Cost Side has 1, Both has 1
        expect(screen.getByText('2')).toBeInTheDocument()
        // Two cards show "1" — Cost Side and Both
        const ones = screen.getAllByText('1')
        expect(ones.length).toBe(2)
    })

    it('shows correct plural/singular labels', () => {
        const onLeverChange = vi.fn()
        render(
            <ValueLeverSummary
                opportunities={mockOpportunities}
                activeLever="All"
                onLeverChange={onLeverChange}
            />
        )

        // Revenue Side has 2 -> "opportunities" (plural)
        expect(screen.getByText('opportunities')).toBeInTheDocument()
        // Cost Side and Both each have 1 -> "opportunity" (singular)
        const singulars = screen.getAllByText('opportunity')
        expect(singulars.length).toBe(2)
    })

    it('clicking a lever card calls onLeverChange', () => {
        const onLeverChange = vi.fn()
        render(
            <ValueLeverSummary
                opportunities={mockOpportunities}
                activeLever="All"
                onLeverChange={onLeverChange}
            />
        )

        const revenueSideCard = screen.getByText('Revenue Side').closest('[class*="card"]')!
        fireEvent.click(revenueSideCard)

        expect(onLeverChange).toHaveBeenCalledWith('Revenue Side')
    })

    it('clicking active lever card calls onLeverChange with "All"', () => {
        const onLeverChange = vi.fn()
        render(
            <ValueLeverSummary
                opportunities={mockOpportunities}
                activeLever="Revenue Side"
                onLeverChange={onLeverChange}
            />
        )

        const revenueSideCard = screen.getByText('Revenue Side').closest('[class*="card"]')!
        fireEvent.click(revenueSideCard)

        expect(onLeverChange).toHaveBeenCalledWith('All')
    })

    it('lever cards are keyboard accessible buttons', () => {
        const onLeverChange = vi.fn()
        render(
            <ValueLeverSummary
                opportunities={mockOpportunities}
                activeLever="All"
                onLeverChange={onLeverChange}
            />
        )

        const revenueButton = screen.getByText('Revenue Side').closest('button')!
        expect(revenueButton).toBeInTheDocument()
        expect(revenueButton.getAttribute('type')).toBe('button')
        expect(revenueButton.getAttribute('aria-pressed')).toBe('false')
    })

    it('aria-pressed reflects active lever', () => {
        const onLeverChange = vi.fn()
        render(
            <ValueLeverSummary
                opportunities={mockOpportunities}
                activeLever="Cost Side"
                onLeverChange={onLeverChange}
            />
        )

        const costButton = screen.getByText('Cost Side').closest('button')!
        expect(costButton.getAttribute('aria-pressed')).toBe('true')

        const revenueButton = screen.getByText('Revenue Side').closest('button')!
        expect(revenueButton.getAttribute('aria-pressed')).toBe('false')
    })

    it('active lever has highlighted background', () => {
        const onLeverChange = vi.fn()
        render(
            <ValueLeverSummary
                opportunities={mockOpportunities}
                activeLever="Cost Side"
                onLeverChange={onLeverChange}
            />
        )

        const costSideCard = screen.getByText('Cost Side').closest('[class*="card"]')!
        // Active card should NOT have the default bg-surface background
        expect(costSideCard).not.toHaveStyle({ background: 'var(--bg-surface)' })

        // Non-active card should have bg-surface background
        const revenueSideCard = screen.getByText('Revenue Side').closest('[class*="card"]')!
        expect(revenueSideCard).toHaveStyle({ background: 'var(--bg-surface)' })
    })
})
