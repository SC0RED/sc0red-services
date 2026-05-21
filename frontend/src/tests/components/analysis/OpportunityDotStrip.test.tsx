import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import OpportunityDotStrip from '@/components/analysis/OpportunityDotStrip'
import type { Opportunity } from '@/lib/types/api'

function buildOpportunity(overrides: Partial<Opportunity> = {}): Opportunity {
    return {
        title: 'Deploy AI chatbot',
        description: 'Reduce L1 ticket volume.',
        impact_rating: 'High',
        timeline: 'Quick Win (1-3 months)',
        strategic_category: 'Operational Efficiency',
        value_lever: 'Revenue Side',
        ...overrides,
    }
}

describe('OpportunityDotStrip', () => {
    it('renders nothing when linkedIndices is undefined', () => {
        const { container } = render(<OpportunityDotStrip linkedIndices={undefined} opportunities={[]} />)
        expect(container).toBeEmptyDOMElement()
    })

    it('renders nothing when linkedIndices is an empty array', () => {
        const { container } = render(
            <OpportunityDotStrip linkedIndices={[]} opportunities={[buildOpportunity()]} />
        )
        expect(container).toBeEmptyDOMElement()
    })

    it('renders nothing when every linkedIndex points past the opportunities array', () => {
        // Stale data: indices reference opportunities that no longer exist
        // (e.g. after a reanalyze cycle shrank the opportunities list).
        // The strip silently drops the missing ones rather than surfacing
        // a "broken link" placeholder.
        const { container } = render(
            <OpportunityDotStrip linkedIndices={[5, 6]} opportunities={[buildOpportunity()]} />
        )
        expect(container).toBeEmptyDOMElement()
    })

    it('renders one dot per linked opportunity in index order', () => {
        const opportunities: Opportunity[] = [
            buildOpportunity({ title: 'A', value_lever: 'Revenue Side' }),
            buildOpportunity({ title: 'B', value_lever: 'Cost Side' }),
            buildOpportunity({ title: 'C', value_lever: 'Both' }),
        ]
        render(<OpportunityDotStrip linkedIndices={[0, 1, 2]} opportunities={opportunities} testId="strip" />)
        const strip = screen.getByTestId('strip')
        const dots = strip.querySelectorAll('span[aria-hidden="true"]')
        expect(dots).toHaveLength(3)
        // Index order is preserved; the title attribute carries the
        // opportunity name + lever for a mouse-hover scan.
        expect(dots[0]).toHaveAttribute('title', 'A (Revenue Side)')
        expect(dots[1]).toHaveAttribute('title', 'B (Cost Side)')
        expect(dots[2]).toHaveAttribute('title', 'C (Both)')
    })

    it('exposes an accessible count via aria-label (singular)', () => {
        render(
            <OpportunityDotStrip linkedIndices={[0]} opportunities={[buildOpportunity({ title: 'Solo' })]} />
        )
        expect(screen.getByRole('img')).toHaveAttribute('aria-label', '1 opportunity targets this')
    })

    it('exposes an accessible count via aria-label (plural)', () => {
        render(
            <OpportunityDotStrip
                linkedIndices={[0, 1]}
                opportunities={[buildOpportunity(), buildOpportunity()]}
            />
        )
        expect(screen.getByRole('img')).toHaveAttribute('aria-label', '2 opportunities target this')
    })

    it('collapses the overflow into a +N badge above maxVisible', () => {
        // Diagnostic Tool Feedback design: when there are more than
        // `maxVisible` linked opportunities, render (maxVisible - 1) dots
        // plus a `+N` overflow badge as the last slot.
        const opportunities = Array.from({ length: 8 }, (_, i) =>
            buildOpportunity({ title: `O${i}`, value_lever: 'Revenue Side' })
        )
        render(
            <OpportunityDotStrip
                linkedIndices={[0, 1, 2, 3, 4, 5, 6, 7]}
                opportunities={opportunities}
                maxVisible={5}
                testId="overflow-strip"
            />
        )
        const strip = screen.getByTestId('overflow-strip')
        // 4 dots + 1 +N badge = 5 spans total (maxVisible).
        const spans = strip.querySelectorAll('span[aria-hidden="true"]')
        expect(spans).toHaveLength(5)
        // The last span is the overflow badge.
        const badge = strip.querySelector('span[tabindex="0"]')
        expect(badge).toHaveTextContent('+4')
        // The badge's title carries the hidden opportunity titles so a
        // mouse-hover scan stays honest.
        expect(badge).toHaveAttribute('title', 'O4\nO5\nO6\nO7')
    })

    it('does not collapse when the linked count equals maxVisible exactly', () => {
        // Edge case: exactly `maxVisible` opportunities should render
        // inline with no overflow badge.
        const opportunities = Array.from({ length: 5 }, (_, i) => buildOpportunity({ title: `O${i}` }))
        render(
            <OpportunityDotStrip
                linkedIndices={[0, 1, 2, 3, 4]}
                opportunities={opportunities}
                maxVisible={5}
                testId="exact-strip"
            />
        )
        const strip = screen.getByTestId('exact-strip')
        const spans = strip.querySelectorAll('span[aria-hidden="true"]')
        expect(spans).toHaveLength(5)
        expect(strip.querySelector('span[tabindex="0"]')).toBeNull()
    })

    it('falls back to --text-secondary for opportunities with no value_lever', () => {
        // `value_lever` is optional on Opportunity. A missing lever doesn't
        // suppress the dot — it just renders in the neutral secondary
        // colour so the user knows "something targets this" even if we
        // don't know the side.
        render(
            <OpportunityDotStrip
                linkedIndices={[0]}
                opportunities={[buildOpportunity({ value_lever: undefined })]}
                testId="no-lever-strip"
            />
        )
        const strip = screen.getByTestId('no-lever-strip')
        const dot = strip.querySelector('span[aria-hidden="true"]') as HTMLElement | null
        expect(dot?.style.background).toBe('var(--text-secondary)')
        // The title also gracefully drops the empty lever paren.
        expect(dot).toHaveAttribute('title', 'Deploy AI chatbot')
    })
})
