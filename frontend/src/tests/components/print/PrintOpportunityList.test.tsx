import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import PrintOpportunityList from '@/components/print/PrintOpportunityList'
import { sortOpportunities } from '@/lib/pdf/sortOpportunities'
import type { Opportunity } from '@/lib/types/api'

const opp = (overrides: Partial<Opportunity>): Opportunity => ({
    title: 'untitled',
    description: 'd',
    impact_rating: 'Low',
    timeline: 't',
    strategic_category: 'Operational Efficiency',
    ...overrides,
})

describe('PrintOpportunityList', () => {
    it('returns null when sortedOpportunities is empty', () => {
        const { container } = render(<PrintOpportunityList sortedOpportunities={[]} />)
        expect(container.firstChild).toBeNull()
    })

    it('groups by lever in the order Revenue → Cost → Both → no-lever', () => {
        const opportunities: Opportunity[] = [
            opp({ title: 'A', impact_rating: 'High', value_lever: 'Cost Side' }),
            opp({ title: 'B', impact_rating: 'High', value_lever: 'Both' }),
            opp({ title: 'C', impact_rating: 'High' }), // no lever
            opp({ title: 'D', impact_rating: 'High', value_lever: 'Revenue Side' }),
        ]
        const { container } = render(
            <PrintOpportunityList sortedOpportunities={sortOpportunities(opportunities)} />
        )
        // Dividers carry a `data-print-lever-divider` attribute so the
        // assertion isn't confused by the lever pill rendered inside
        // each card (which uses the same label text).
        const dividerLabels = Array.from(container.querySelectorAll('[data-print-lever-divider]')).map(
            (node) => (node as HTMLElement).getAttribute('data-print-lever-divider')
        )
        expect(dividerLabels).toEqual(['Revenue Side', 'Cost Side', 'Both', 'Other'])
    })

    it('skips groups that have no opportunities', () => {
        const opportunities: Opportunity[] = [
            opp({ title: 'A', impact_rating: 'High', value_lever: 'Cost Side' }),
        ]
        const { container } = render(
            <PrintOpportunityList sortedOpportunities={sortOpportunities(opportunities)} />
        )
        const dividerLabels = Array.from(container.querySelectorAll('[data-print-lever-divider]')).map(
            (node) => (node as HTMLElement).getAttribute('data-print-lever-divider')
        )
        expect(dividerLabels).toEqual(['Cost Side'])
    })

    it('threads printedIndex through to each card so cross-references remain stable', () => {
        const opportunities: Opportunity[] = [
            opp({ title: 'low-A', impact_rating: 'Low', value_lever: 'Cost Side' }),
            opp({ title: 'high-B', impact_rating: 'High', value_lever: 'Revenue Side' }),
        ]
        render(<PrintOpportunityList sortedOpportunities={sortOpportunities(opportunities)} />)
        // After sorting, "high-B" is printedIndex 1; "low-A" is printedIndex 2.
        expect(screen.getByText('#1')).toBeInTheDocument()
        expect(screen.getByText('#2')).toBeInTheDocument()
    })

    it('renders the section heading', () => {
        const opportunities: Opportunity[] = [opp({ title: 'X', impact_rating: 'High' })]
        render(<PrintOpportunityList sortedOpportunities={sortOpportunities(opportunities)} />)
        expect(screen.getByText('AI Opportunity Roadmap')).toBeInTheDocument()
    })
})
