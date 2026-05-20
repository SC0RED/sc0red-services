import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import QuickWinsMatrix from '@/components/analysis/QuickWinsMatrix'
import { OpportunityHoverProvider, useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import type { Opportunity } from '@/lib/types/api'

const make = (overrides: Partial<Opportunity>): Opportunity => ({
    title: 'Test opportunity',
    description: 'desc',
    impact_rating: 'High',
    timeline: 'Quick Win (1-3 months)',
    strategic_category: 'Operational Efficiency',
    value_lever: 'Revenue Side',
    ...overrides,
})

/** Probe component exposing provider state via test-readable DOM. */
function HoverProbe() {
    const { hoveredOpportunityIndices } = useOpportunityHover()
    return <div data-testid="hover-probe" data-indices={hoveredOpportunityIndices.join(',')} />
}

describe('QuickWinsMatrix — structural rendering', () => {
    it('renders all three column headers in left-to-right timeline order', () => {
        render(<QuickWinsMatrix opportunities={[]} />)
        expect(screen.getByTestId('quick-wins-column-header-0')).toHaveTextContent('Quick Win')
        expect(screen.getByTestId('quick-wins-column-header-1')).toHaveTextContent('Medium-term')
        expect(screen.getByTestId('quick-wins-column-header-2')).toHaveTextContent('Long-term')
    })

    it('renders all three row headers in top-to-bottom impact order', () => {
        render(<QuickWinsMatrix opportunities={[]} />)
        expect(screen.getByTestId('quick-wins-row-header-0')).toHaveTextContent('High impact')
        expect(screen.getByTestId('quick-wins-row-header-1')).toHaveTextContent('Medium impact')
        expect(screen.getByTestId('quick-wins-row-header-2')).toHaveTextContent('Low impact')
    })

    it('places quadrant labels in the four corner cells', () => {
        render(<QuickWinsMatrix opportunities={[]} />)
        expect(screen.getByTestId('quick-wins-cell-0-0')).toHaveTextContent('Quick Wins')
        expect(screen.getByTestId('quick-wins-cell-0-2')).toHaveTextContent('Strategic Bets')
        expect(screen.getByTestId('quick-wins-cell-2-0')).toHaveTextContent('Fill-Ins')
        expect(screen.getByTestId('quick-wins-cell-2-2')).toHaveTextContent('Deprioritise')
    })

    it('center-axis cells have no quadrant label', () => {
        render(<QuickWinsMatrix opportunities={[]} />)
        const center = screen.getByTestId('quick-wins-cell-1-1')
        // None of the four quadrant labels should appear inside.
        expect(within(center).queryByText(/Quick Wins|Strategic Bets|Fill-Ins|Deprioritise/)).toBeNull()
    })
})

describe('QuickWinsMatrix — dot rendering', () => {
    it('places a single High × Quick opportunity in the top-left cell with its title visible inline', () => {
        const opps = [make({ title: 'Roll out signature beverage' })]
        render(<QuickWinsMatrix opportunities={opps} />)
        const cell = screen.getByTestId('quick-wins-cell-0-0')
        const chip = within(cell).getByTestId('quick-wins-dot-0')
        expect(chip).toBeInTheDocument()
        // Title is rendered inline in the chip (no hover required).
        expect(chip).toHaveTextContent('Roll out signature beverage')
    })

    it('places three opportunities in the same cell as three title chips', () => {
        const opps = [
            make({ title: 'A-title', strategic_category: 'A', impact_rating: 'High', timeline: 'Quick Win' }),
            make({ title: 'B-title', strategic_category: 'B', impact_rating: 'High', timeline: 'Quick Win' }),
            make({ title: 'C-title', strategic_category: 'C', impact_rating: 'High', timeline: 'Quick Win' }),
        ]
        render(<QuickWinsMatrix opportunities={opps} />)
        const cell = screen.getByTestId('quick-wins-cell-0-0')
        expect(within(cell).getByText('A-title')).toBeInTheDocument()
        expect(within(cell).getByText('B-title')).toBeInTheDocument()
        expect(within(cell).getByText('C-title')).toBeInTheDocument()
    })

    it('renders 4 chips + a +N more badge when a cell has 10 opportunities', () => {
        // Chip threshold (MAX_VISIBLE_CHIPS = 4) is lower than the
        // original dot threshold (7) because title chips take ~3× the
        // vertical real estate per item.
        const opps = Array.from({ length: 10 }, (_, i) =>
            make({
                title: `Opp ${i}`,
                strategic_category: `cat-${i}`,
                impact_rating: 'High',
                timeline: 'Quick Win',
            })
        )
        render(<QuickWinsMatrix opportunities={opps} />)
        const cell = screen.getByTestId('quick-wins-cell-0-0')
        const chips = within(cell).getAllByTestId(/^quick-wins-dot-/)
        expect(chips).toHaveLength(4)
        // Overflow badge counts the remaining 6.
        expect(within(cell).getByTestId('quick-wins-overflow-badge')).toHaveTextContent('+6 more')
    })

    it('opens a popover listing all 10 opportunities when the +N badge is clicked', () => {
        const opps = Array.from({ length: 10 }, (_, i) =>
            make({
                title: `Opp ${i}`,
                strategic_category: `cat-${i}`,
                impact_rating: 'High',
                timeline: 'Quick Win',
            })
        )
        render(<QuickWinsMatrix opportunities={opps} />)
        const cell = screen.getByTestId('quick-wins-cell-0-0')
        fireEvent.click(within(cell).getByTestId('quick-wins-overflow-badge'))

        const popover = screen.getByTestId('quick-wins-overflow-popover')
        for (let i = 0; i < 10; i += 1) {
            expect(within(popover).getByText(`Opp ${i}`)).toBeInTheDocument()
        }
    })

    it('suppresses the dev-mode console.warn from showing in test output', () => {
        // Render a matrix with an unrecognised timeline to trigger
        // the bucketing warning. This test exists only to keep the
        // suite's stderr clean — it asserts the warn fires once and
        // then restores the spy. Behavioural assertion lives in the
        // layout helper's own test file.
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
        render(<QuickWinsMatrix opportunities={[make({ timeline: 'Unspecified' })]} />)
        expect(warnSpy).toHaveBeenCalledOnce()
        warnSpy.mockRestore()
    })
})

describe('QuickWinsMatrix — hover wiring', () => {
    it('dispatches the opportunity index on dot click', () => {
        render(
            <OpportunityHoverProvider>
                <QuickWinsMatrix opportunities={[make({}), make({ title: 'second' })]} />
                <HoverProbe />
            </OpportunityHoverProvider>
        )
        fireEvent.click(screen.getByTestId('quick-wins-dot-1'))
        expect(screen.getByTestId('hover-probe').getAttribute('data-indices')).toBe('1')
    })

    it('dispatches on mouseEnter and clears on mouseLeave', () => {
        render(
            <OpportunityHoverProvider>
                <QuickWinsMatrix opportunities={[make({})]} />
                <HoverProbe />
            </OpportunityHoverProvider>
        )
        const dot = screen.getByTestId('quick-wins-dot-0')
        const probe = () => screen.getByTestId('hover-probe').getAttribute('data-indices')

        expect(probe()).toBe('')
        fireEvent.mouseEnter(dot)
        expect(probe()).toBe('0')
        fireEvent.mouseLeave(dot)
        expect(probe()).toBe('')
    })

    it('dispatches on focus and clears on blur for keyboard users', () => {
        render(
            <OpportunityHoverProvider>
                <QuickWinsMatrix opportunities={[make({})]} />
                <HoverProbe />
            </OpportunityHoverProvider>
        )
        const dot = screen.getByTestId('quick-wins-dot-0')
        fireEvent.focus(dot)
        expect(screen.getByTestId('hover-probe').getAttribute('data-indices')).toBe('0')
        fireEvent.blur(dot)
        expect(screen.getByTestId('hover-probe').getAttribute('data-indices')).toBe('')
    })
})

describe('QuickWinsMatrix — overflow popover keyboard + outside-click', () => {
    let warnSpy: ReturnType<typeof vi.spyOn>
    beforeEach(() => {
        warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    })
    afterEach(() => {
        warnSpy.mockRestore()
    })

    function renderOverflow() {
        const opps = Array.from({ length: 10 }, (_, i) =>
            make({ title: `Opp ${i}`, strategic_category: `cat-${i}` })
        )
        return render(
            <OpportunityHoverProvider>
                <QuickWinsMatrix opportunities={opps} />
                <HoverProbe />
            </OpportunityHoverProvider>
        )
    }

    it('closes on Escape', () => {
        renderOverflow()
        fireEvent.click(screen.getByTestId('quick-wins-overflow-badge'))
        const popover = screen.getByTestId('quick-wins-overflow-popover')
        fireEvent.keyDown(popover, { key: 'Escape' })
        expect(screen.queryByTestId('quick-wins-overflow-popover')).toBeNull()
    })

    it('clicking a popover item dispatches that opportunity highlight and closes the popover', () => {
        renderOverflow()
        fireEvent.click(screen.getByTestId('quick-wins-overflow-badge'))
        fireEvent.click(screen.getByTestId('quick-wins-popover-item-9'))
        expect(screen.getByTestId('hover-probe').getAttribute('data-indices')).toBe('9')
        expect(screen.queryByTestId('quick-wins-overflow-popover')).toBeNull()
    })

    it('outside click closes the popover', () => {
        const { container } = renderOverflow()
        fireEvent.click(screen.getByTestId('quick-wins-overflow-badge'))
        expect(screen.getByTestId('quick-wins-overflow-popover')).toBeInTheDocument()
        // Click on the container root (outside the popover).
        fireEvent.mouseDown(container)
        expect(screen.queryByTestId('quick-wins-overflow-popover')).toBeNull()
    })
})

describe('QuickWinsMatrix — click navigates to opportunity card', () => {
    /**
     * Regression test for the scroll-on-hover bug surfaced in post-P1b
     * review. Hover sources (strategy map, EBITDA, value chain) no
     * longer trigger ``scrollIntoView``; only intentional navigation
     * (clicking a Quick Wins matrix chip) scrolls the matching
     * opportunity card into view.
     *
     * jsdom doesn't lay out, so we spy on ``scrollIntoView`` and assert
     * the call happened with the right options against the right
     * element.
     */

    it('clicking a chip imperatively scrolls the matching opportunity card into view', () => {
        const scrollSpy = vi.spyOn(Element.prototype, 'scrollIntoView')

        // Render the matrix alongside a stand-in for the opportunity
        // card that ``HoverableOpportunityCard`` would emit. The click
        // handler queries by ``data-testid="opportunity-card-{n}"`` so
        // any element with that testid is a valid scroll target.
        const opps = [make({ title: 'First opp' }), make({ title: 'Second opp' })]
        render(
            <>
                <QuickWinsMatrix opportunities={opps} />
                <div data-testid="opportunity-card-1">Second opp card</div>
            </>
        )
        scrollSpy.mockClear()

        fireEvent.click(screen.getByTestId('quick-wins-dot-1'))

        expect(scrollSpy).toHaveBeenCalledWith({
            behavior: 'smooth',
            block: 'nearest',
        })
    })

    it('hovering a chip does NOT scroll (hover pulses only)', () => {
        const scrollSpy = vi.spyOn(Element.prototype, 'scrollIntoView')
        render(<QuickWinsMatrix opportunities={[make({})]} />)
        scrollSpy.mockClear()

        fireEvent.mouseEnter(screen.getByTestId('quick-wins-dot-0'))

        expect(scrollSpy).not.toHaveBeenCalled()
    })
})
