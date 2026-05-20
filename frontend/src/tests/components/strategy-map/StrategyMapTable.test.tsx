import { fireEvent, render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import StrategyMapTable from '@/components/strategy-map/StrategyMapTable'
import { OpportunityHoverProvider, useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import type { Opportunity, StrategyMap } from '@/lib/types/api'
import { fullStrategyMap } from './_fixtures'

/**
 * Tests for the Phase-6 CSS-grid Balanced Scorecard table renderer.
 * Covers:
 *   - column-header row rendering
 *   - perspective-row routing (one row per perspective in canonical order)
 *   - per-cell objective rendering (title + first-sentence definition)
 *   - opportunity dot-strip presence (only when linked indices resolve)
 *   - hover wiring → ``OpportunityHoverProvider`` dispatches the
 *     objective's ``linked_opportunity_indices`` on mouse-enter / focus
 *     and clears on mouse-leave / blur
 */

const OPPS: Opportunity[] = [
    {
        title: 'Roll out signature beverage',
        description: 'New cold-brew platform',
        impact_rating: 'High',
        timeline: '3 months',
        strategic_category: 'Revenue Growth',
        value_lever: 'Revenue Side',
    },
    {
        title: 'Cut warehouse staffing costs',
        description: 'Schedule against actual demand',
        impact_rating: 'Medium',
        timeline: '6 months',
        strategic_category: 'Operational Efficiency',
        value_lever: 'Cost Side',
    },
]

/**
 * Strategy-map fixture with a single financial objective carrying
 * linked_opportunity_indices [0]. Used to assert dot rendering + hover
 * dispatch on a known target.
 */
const linkedStrategyMap: StrategyMap = {
    ...fullStrategyMap,
    financial: {
        objectives: [
            {
                ...fullStrategyMap.financial.objectives[0],
                id: 'F1',
                linked_opportunity_indices: [0],
            },
        ],
    },
}

/** Probe component exposing provider state via test-readable DOM. */
function HoverProbe() {
    const { hoveredOpportunityIndices } = useOpportunityHover()
    return <div data-testid="hover-probe" data-indices={hoveredOpportunityIndices.join(',')} />
}

describe('StrategyMapTable — structural rendering', () => {
    it('renders one column header per theme', () => {
        render(<StrategyMapTable strategyMap={fullStrategyMap} opportunities={OPPS} />)
        expect(screen.getByTestId('strategy-map-theme-header-0')).toHaveTextContent(
            'Grow Through Foodservice'
        )
        expect(screen.getByTestId('strategy-map-theme-header-1')).toHaveTextContent(
            'Deliver Convenience and Value'
        )
    })

    it('renders one row per perspective in canonical Kaplan-Norton order', () => {
        render(<StrategyMapTable strategyMap={fullStrategyMap} opportunities={OPPS} />)
        expect(screen.getByTestId('strategy-map-row-financial')).toBeInTheDocument()
        expect(screen.getByTestId('strategy-map-row-customer')).toBeInTheDocument()
        expect(screen.getByTestId('strategy-map-row-internal')).toBeInTheDocument()
        expect(screen.getByTestId('strategy-map-row-capacity')).toBeInTheDocument()
    })

    it('renders an objective entry with title + first-sentence definition preview', () => {
        render(<StrategyMapTable strategyMap={fullStrategyMap} opportunities={OPPS} />)
        const f1 = screen.getByTestId('strategy-map-objective-F1')
        expect(f1).toHaveTextContent('Grow profitable revenue across markets')
        // Only the first sentence of the definition is rendered visibly
        // (full text is exposed via the article's title attribute).
        expect(f1).toHaveTextContent(/^.*?[.!?]/)
    })
})

describe('StrategyMapTable — opportunity dot strip', () => {
    it('does NOT render a legend when no objective carries any linked index', () => {
        render(<StrategyMapTable strategyMap={fullStrategyMap} opportunities={OPPS} />)
        expect(screen.queryByTestId('strategy-map-opportunity-link-legend')).not.toBeInTheDocument()
    })

    it('renders a legend when at least one objective resolves an in-range linked index', () => {
        render(<StrategyMapTable strategyMap={linkedStrategyMap} opportunities={OPPS} />)
        expect(screen.getByTestId('strategy-map-opportunity-link-legend')).toBeInTheDocument()
    })

    it('renders the per-objective dot strip wrapper for the linked objective', () => {
        render(<StrategyMapTable strategyMap={linkedStrategyMap} opportunities={OPPS} />)
        expect(screen.getByTestId('strategy-map-linked-opportunity-dots-F1')).toBeInTheDocument()
    })
})

describe('StrategyMapTable — hover wiring', () => {
    it('dispatches linked indices to the provider on mouse-enter and clears on mouse-leave', () => {
        render(
            <OpportunityHoverProvider>
                <StrategyMapTable strategyMap={linkedStrategyMap} opportunities={OPPS} />
                <HoverProbe />
            </OpportunityHoverProvider>
        )
        const article = screen.getByTestId('strategy-map-objective-F1')
        const probe = () => screen.getByTestId('hover-probe').getAttribute('data-indices')

        expect(probe()).toBe('')

        fireEvent.mouseEnter(article)
        expect(probe()).toBe('0')

        fireEvent.mouseLeave(article)
        expect(probe()).toBe('')
    })

    it('does not dispatch when an objective has no linked indices', () => {
        // Without the early-return guard the provider would treat every
        // hover as authoritative and clear whatever the previous source
        // had highlighted. The guard keeps unlinked objectives inert.
        render(
            <OpportunityHoverProvider>
                <StrategyMapTable strategyMap={fullStrategyMap} opportunities={OPPS} />
                <HoverProbe />
            </OpportunityHoverProvider>
        )
        const article = screen.getByTestId('strategy-map-objective-F1')
        fireEvent.mouseEnter(article)
        expect(screen.getByTestId('hover-probe').getAttribute('data-indices')).toBe('')
    })

    it('dispatches on focus and clears on blur for keyboard users', () => {
        render(
            <OpportunityHoverProvider>
                <StrategyMapTable strategyMap={linkedStrategyMap} opportunities={OPPS} />
                <HoverProbe />
            </OpportunityHoverProvider>
        )
        const article = screen.getByTestId('strategy-map-objective-F1')

        fireEvent.focus(article)
        expect(screen.getByTestId('hover-probe').getAttribute('data-indices')).toBe('0')

        fireEvent.blur(article)
        expect(screen.getByTestId('hover-probe').getAttribute('data-indices')).toBe('')
    })

    it('renders empty cells as placeholders so the grid alignment stays', () => {
        // With 2 themes and 3 capacity entries (P/T/C) round-robined,
        // every cell is filled. Use a custom map with 4 themes so a
        // capacity placeholder must render.
        const fourThemeMap: StrategyMap = {
            ...fullStrategyMap,
            internalProcesses: {
                themes: [
                    fullStrategyMap.internalProcesses.themes[0],
                    fullStrategyMap.internalProcesses.themes[1],
                    {
                        name: 'Adjacent Markets',
                        supports_financial_objectives: [],
                        objectives: [],
                    },
                    {
                        name: 'Cost Discipline',
                        supports_financial_objectives: [],
                        objectives: [],
                    },
                ],
            },
        }
        render(<StrategyMapTable strategyMap={fourThemeMap} opportunities={OPPS} />)
        // capacity row, column 3 has no objective → placeholder testid
        expect(screen.getByTestId('strategy-map-cell-capacity-3-empty')).toBeInTheDocument()
    })
})
