import { render, screen, within } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'

import PrintQuickWinsMatrix from '@/components/print/PrintQuickWinsMatrix'
import { sortOpportunities, type OpportunityWithIndex } from '@/lib/pdf/sortOpportunities'
import type { Opportunity } from '@/lib/types/api'

/**
 * Tests for the print variant of the Quick Wins matrix. The print
 * component renders the same layout / quadrant labels as the screen
 * variant but without event handlers and with a per-cell list of
 * #printedIndex (title) entries under each dot stack so the dot ↔
 * opportunity linkage survives the export.
 */

const make = (overrides: Partial<Opportunity>): Opportunity => ({
    title: 'Test opportunity',
    description: 'desc',
    impact_rating: 'High',
    timeline: 'Quick Win (1-3 months)',
    strategic_category: 'Operational Efficiency',
    value_lever: 'Revenue Side',
    ...overrides,
})

function renderWith(opportunities: Opportunity[]) {
    const sortedOpportunities: OpportunityWithIndex[] = sortOpportunities(opportunities)
    return render(<PrintQuickWinsMatrix sortedOpportunities={sortedOpportunities} />)
}

describe('PrintQuickWinsMatrix — structural rendering', () => {
    it('renders the section heading', () => {
        renderWith([])
        expect(screen.getByRole('heading', { name: /Quick Wins Matrix/i })).toBeInTheDocument()
    })

    it('renders quadrant labels in the four corners', () => {
        renderWith([])
        expect(screen.getByText('Quick Wins')).toBeInTheDocument()
        expect(screen.getByText('Strategic Bets')).toBeInTheDocument()
        expect(screen.getByText('Fill-Ins')).toBeInTheDocument()
        expect(screen.getByText('Deprioritise')).toBeInTheDocument()
    })

    it('renders dots for each opportunity', () => {
        const opps = [
            make({ title: 'Opp A', impact_rating: 'High', timeline: 'Quick Win' }),
            make({ title: 'Opp B', impact_rating: 'Low', timeline: 'Long-term' }),
        ]
        const { container } = renderWith(opps)
        // Both dots survive into the static print DOM.
        expect(container.textContent).toContain('Opp A')
        expect(container.textContent).toContain('Opp B')
    })

    it('lists printed-index references under each dot stack', () => {
        // Two opportunities, both High × Quick: should both land in
        // the top-left cell with their printed-index references shown.
        const opps = [
            make({ title: 'Opp A', impact_rating: 'High', timeline: 'Quick Win' }),
            make({ title: 'Opp B', impact_rating: 'High', timeline: 'Quick Win' }),
        ]
        const { container } = renderWith(opps)
        expect(container.textContent).toMatch(/#1 Opp [AB]/)
        expect(container.textContent).toMatch(/#2 Opp [AB]/)
    })
})

describe('PrintQuickWinsMatrix — interactivity stripped', () => {
    it('renders no buttons in the print DOM (no hover, no popover)', () => {
        const opps = Array.from({ length: 10 }, (_, i) =>
            make({ title: `Opp ${i}`, strategic_category: `cat-${i}` })
        )
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
        const { container } = render(<PrintQuickWinsMatrix sortedOpportunities={sortOpportunities(opps)} />)
        // No <button> elements: the screen QuickWinsMatrix uses buttons
        // for the dots + overflow badge + popover items; the print
        // variant must not.
        expect(container.querySelectorAll('button').length).toBe(0)
        warnSpy.mockRestore()
    })

    it('does not render an overflow popover for cells with many opportunities', () => {
        // Print path has no popover state — all opportunities are
        // listed inline under the dot stack regardless of count.
        const opps = Array.from({ length: 10 }, (_, i) =>
            make({ title: `Opp ${i}`, strategic_category: `cat-${i}` })
        )
        renderWith(opps)
        expect(screen.queryByTestId('quick-wins-overflow-popover')).toBeNull()
        expect(screen.queryByTestId('quick-wins-overflow-badge')).toBeNull()
    })

    it('lists every opportunity title in the cell list even when the count exceeds the screen overflow threshold', () => {
        const opps = Array.from({ length: 10 }, (_, i) =>
            make({ title: `Opp ${i}`, strategic_category: `cat-${i}` })
        )
        const { container } = renderWith(opps)
        for (let i = 0; i < 10; i += 1) {
            expect(within(container).getByText(new RegExp(`Opp ${i}\\b`))).toBeInTheDocument()
        }
    })
})
