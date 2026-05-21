import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'

import QuickWinsMatrix from '@/components/analysis/QuickWinsMatrix'
import { OpportunityHoverProvider, useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import type { Opportunity } from '@/lib/types/api'
import { CLUSTER_THRESHOLD } from '@/lib/utils/quickWinsMatrixLayout'

/**
 * Tests for the Phase-14 ROI × Investment matrix (path B). The
 * component projects each opportunity onto a log-scale investment
 * (X) × linear ROI (Y) scatter plot inside an SVG. Opportunities with
 * either numeric axis missing route to the separate uncalibrated
 * strip beneath the plot.
 *
 * Test ids exposed by the component:
 *
 *   quick-wins-matrix                   — outer container
 *   quick-wins-matrix-svg               — the SVG plot
 *   quick-wins-dot-{n}                  — individual in-plot dot
 *   quick-wins-cluster-{quadrant}       — cluster pin (when > threshold)
 *   quick-wins-cluster-popover-{quad}   — cluster popover (when open)
 *   quick-wins-cluster-item-{q}-{n}     — popover entry
 *   quick-wins-uncalibrated-strip       — footer strip (when non-empty)
 *   quick-wins-uncalibrated-dot-{n}     — uncalibrated dot
 *   quick-wins-quadrant-label-{quad}    — corner quadrant label
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

/** Probe component exposing provider state via test-readable DOM. */
function HoverProbe() {
    const { hoveredOpportunityIndices } = useOpportunityHover()
    return <div data-testid="hover-probe" data-indices={hoveredOpportunityIndices.join(',')} />
}

// ── Structural rendering ──────────────────────────────────────────

describe('QuickWinsMatrix — structural rendering', () => {
    it('renders the outer container, SVG, and four corner quadrant labels', () => {
        render(<QuickWinsMatrix opportunities={[]} />)
        expect(screen.getByTestId('quick-wins-matrix')).toBeInTheDocument()
        expect(screen.getByTestId('quick-wins-matrix-svg')).toBeInTheDocument()
        expect(screen.getByTestId('quick-wins-quadrant-label-quick-wins')).toHaveTextContent(/QUICK WINS/i)
        expect(screen.getByTestId('quick-wins-quadrant-label-strategic-bets')).toHaveTextContent(
            /STRATEGIC BETS/i
        )
        expect(screen.getByTestId('quick-wins-quadrant-label-fill-ins')).toHaveTextContent(/FILL-INS/i)
        expect(screen.getByTestId('quick-wins-quadrant-label-deprioritise')).toHaveTextContent(
            /DEPRIORITISE/i
        )
    })

    it('renders log-scale X-axis tick labels at $10K, $100K, $1M, $10M', () => {
        render(<QuickWinsMatrix opportunities={[]} />)
        const svg = screen.getByTestId('quick-wins-matrix-svg')
        expect(within(svg).getByText('$10K')).toBeInTheDocument()
        expect(within(svg).getByText('$100K')).toBeInTheDocument()
        expect(within(svg).getByText('$1M')).toBeInTheDocument()
        expect(within(svg).getByText('$10M')).toBeInTheDocument()
    })

    it('renders linear Y-axis tick labels at 0%, 100%, 200%, 300%', () => {
        render(<QuickWinsMatrix opportunities={[]} />)
        const svg = screen.getByTestId('quick-wins-matrix-svg')
        // Each tick is rendered as a text element containing
        // "{value}%". With four ticks we expect four matches.
        expect(within(svg).getByText('0%')).toBeInTheDocument()
        expect(within(svg).getByText('100%')).toBeInTheDocument()
        expect(within(svg).getByText('200%')).toBeInTheDocument()
        expect(within(svg).getByText('300%')).toBeInTheDocument()
    })

    it('renders axis titles', () => {
        render(<QuickWinsMatrix opportunities={[]} />)
        const svg = screen.getByTestId('quick-wins-matrix-svg')
        expect(within(svg).getByText(/Investment \(USD, log scale\)/)).toBeInTheDocument()
        expect(within(svg).getByText(/ROI \(%\)/)).toBeInTheDocument()
    })

    it('does not render the uncalibrated strip when every opportunity has both axes', () => {
        render(
            <QuickWinsMatrix
                opportunities={[make({ investment_value_usd: 100_000, roi_estimate_pct: 150 })]}
            />
        )
        expect(screen.queryByTestId('quick-wins-uncalibrated-strip')).toBeNull()
    })
})

// ── In-plot dot routing ───────────────────────────────────────────

describe('QuickWinsMatrix — in-plot dot routing', () => {
    it('renders an in-plot dot for opportunities with both numeric axes populated', () => {
        render(
            <QuickWinsMatrix
                opportunities={[
                    make({
                        title: 'Roll out signature beverage',
                        investment_value_usd: 100_000,
                        roi_estimate_pct: 150,
                    }),
                ]}
            />
        )
        expect(screen.getByTestId('quick-wins-dot-0')).toBeInTheDocument()
        expect(screen.queryByTestId('quick-wins-uncalibrated-strip')).toBeNull()
    })

    it('renders multiple in-plot dots, one per opportunity', () => {
        render(
            <QuickWinsMatrix
                opportunities={[
                    make({ title: 'A', investment_value_usd: 50_000, roi_estimate_pct: 200 }),
                    make({ title: 'B', investment_value_usd: 200_000, roi_estimate_pct: 80 }),
                    make({ title: 'C', investment_value_usd: 500_000, roi_estimate_pct: 40 }),
                ]}
            />
        )
        expect(screen.getByTestId('quick-wins-dot-0')).toBeInTheDocument()
        expect(screen.getByTestId('quick-wins-dot-1')).toBeInTheDocument()
        expect(screen.getByTestId('quick-wins-dot-2')).toBeInTheDocument()
    })

    it('renders the dot title via the SVG <title> tooltip (lever in parens)', () => {
        render(
            <QuickWinsMatrix
                opportunities={[
                    make({
                        title: 'Roll out signature beverage',
                        value_lever: 'Cost Side',
                        investment_value_usd: 100_000,
                        roi_estimate_pct: 150,
                    }),
                ]}
            />
        )
        const dot = screen.getByTestId('quick-wins-dot-0')
        // <title> is the SVG-native tooltip element.
        expect(dot.querySelector('title')).toHaveTextContent('Roll out signature beverage (Cost Side)')
    })

    it('exposes an aria-label and role="button" for screen reader users', () => {
        render(
            <QuickWinsMatrix
                opportunities={[
                    make({
                        title: 'Cut SaaS sprawl',
                        investment_value_usd: 100_000,
                        roi_estimate_pct: 150,
                    }),
                ]}
            />
        )
        const dot = screen.getByTestId('quick-wins-dot-0')
        expect(dot).toHaveAttribute('role', 'button')
        expect(dot).toHaveAttribute('aria-label', 'Highlight opportunity: Cut SaaS sprawl')
    })

    it('renders a clamp caret when ROI exceeds the visual cap', () => {
        render(
            <QuickWinsMatrix
                opportunities={[make({ investment_value_usd: 100_000, roi_estimate_pct: 450 })]}
            />
        )
        // The caret is a child text node "↑" inside the dot group.
        const dot = screen.getByTestId('quick-wins-dot-0')
        expect(dot.textContent).toContain('↑')
    })

    it('renders an inline title label next to the dot so the chart is readable without hover', () => {
        render(
            <QuickWinsMatrix
                opportunities={[
                    make({
                        title: 'Cut SaaS sprawl',
                        investment_value_usd: 100_000,
                        roi_estimate_pct: 150,
                    }),
                ]}
            />
        )
        const label = screen.getByTestId('quick-wins-dot-label-0')
        expect(label).toHaveTextContent('Cut SaaS sprawl')
    })

    it('truncates long titles in the inline dot label with an ellipsis', () => {
        // 30-char title; the inline label budget is 22 chars, so we
        // expect a "…" suffix and a shortened prefix.
        render(
            <QuickWinsMatrix
                opportunities={[
                    make({
                        title: 'Deploy AI churn prediction model end-to-end',
                        investment_value_usd: 100_000,
                        roi_estimate_pct: 150,
                    }),
                ]}
            />
        )
        const label = screen.getByTestId('quick-wins-dot-label-0')
        // Truncation produces "Deploy AI churn predi…" (21 chars + ellipsis).
        expect(label.textContent ?? '').toMatch(/…$/)
        expect((label.textContent ?? '').length).toBeLessThanOrEqual(22)
        // The full title still appears in the SVG <title> tooltip + aria-label,
        // so screen readers and hover-tooltip users get the unabridged text.
        const dot = screen.getByTestId('quick-wins-dot-0')
        expect(dot.querySelector('title')?.textContent).toContain(
            'Deploy AI churn prediction model end-to-end'
        )
    })

    it('does NOT render the clamp caret for in-range ROI values', () => {
        render(
            <QuickWinsMatrix
                opportunities={[make({ investment_value_usd: 100_000, roi_estimate_pct: 150 })]}
            />
        )
        const dot = screen.getByTestId('quick-wins-dot-0')
        expect(dot.textContent ?? '').not.toContain('↑')
    })
})

// ── Uncalibrated strip routing ────────────────────────────────────

describe('QuickWinsMatrix — uncalibrated strip routing', () => {
    it('routes opportunities missing investment_value_usd into the uncalibrated strip', () => {
        render(
            <QuickWinsMatrix
                opportunities={[
                    make({
                        title: 'Mystery opp',
                        investment_value_usd: null,
                        roi_estimate_pct: 150,
                    }),
                ]}
            />
        )
        const strip = screen.getByTestId('quick-wins-uncalibrated-strip')
        expect(within(strip).getByTestId('quick-wins-uncalibrated-dot-0')).toBeInTheDocument()
        expect(screen.queryByTestId('quick-wins-dot-0')).toBeNull()
    })

    it('routes opportunities missing roi_estimate_pct into the uncalibrated strip', () => {
        render(
            <QuickWinsMatrix
                opportunities={[make({ investment_value_usd: 100_000, roi_estimate_pct: null })]}
            />
        )
        const strip = screen.getByTestId('quick-wins-uncalibrated-strip')
        expect(within(strip).getByTestId('quick-wins-uncalibrated-dot-0')).toBeInTheDocument()
    })

    it('routes opportunities missing both axes into the uncalibrated strip', () => {
        render(
            <QuickWinsMatrix opportunities={[make({ investment_value_usd: null, roi_estimate_pct: null })]} />
        )
        expect(screen.getByTestId('quick-wins-uncalibrated-dot-0')).toBeInTheDocument()
    })

    it('treats undefined-valued axes the same as null (legacy persisted shape)', () => {
        render(<QuickWinsMatrix opportunities={[make({})]} />)
        // make() leaves both axes off (undefined), simulating a record
        // persisted before the Phase-14 schema migration. The component
        // routes these to the uncalibrated strip.
        expect(screen.getByTestId('quick-wins-uncalibrated-dot-0')).toBeInTheDocument()
    })

    it('renders mixed in-plot + uncalibrated opportunities side by side', () => {
        render(
            <QuickWinsMatrix
                opportunities={[
                    make({
                        title: 'Sized',
                        investment_value_usd: 100_000,
                        roi_estimate_pct: 150,
                    }),
                    make({
                        title: 'Unsized',
                        investment_value_usd: null,
                        roi_estimate_pct: null,
                    }),
                ]}
            />
        )
        expect(screen.getByTestId('quick-wins-dot-0')).toBeInTheDocument()
        expect(screen.getByTestId('quick-wins-uncalibrated-dot-1')).toBeInTheDocument()
    })
})

// ── Hover wiring (dots + uncalibrated) ───────────────────────────

describe('QuickWinsMatrix — hover wiring', () => {
    it('dispatches the opportunity index on dot mouseEnter and clears on mouseLeave', () => {
        render(
            <OpportunityHoverProvider>
                <QuickWinsMatrix
                    opportunities={[make({ investment_value_usd: 100_000, roi_estimate_pct: 150 })]}
                />
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

    it('dispatches on focus and clears on blur (keyboard users)', () => {
        render(
            <OpportunityHoverProvider>
                <QuickWinsMatrix
                    opportunities={[make({ investment_value_usd: 100_000, roi_estimate_pct: 150 })]}
                />
                <HoverProbe />
            </OpportunityHoverProvider>
        )
        const dot = screen.getByTestId('quick-wins-dot-0')
        fireEvent.focus(dot)
        expect(screen.getByTestId('hover-probe').getAttribute('data-indices')).toBe('0')
        fireEvent.blur(dot)
        expect(screen.getByTestId('hover-probe').getAttribute('data-indices')).toBe('')
    })

    it('dispatches on uncalibrated-dot mouseEnter and clears on mouseLeave', () => {
        render(
            <OpportunityHoverProvider>
                <QuickWinsMatrix
                    opportunities={[make({ investment_value_usd: null, roi_estimate_pct: null })]}
                />
                <HoverProbe />
            </OpportunityHoverProvider>
        )
        const dot = screen.getByTestId('quick-wins-uncalibrated-dot-0')
        const probe = () => screen.getByTestId('hover-probe').getAttribute('data-indices')

        fireEvent.mouseEnter(dot)
        expect(probe()).toBe('0')
        fireEvent.mouseLeave(dot)
        expect(probe()).toBe('')
    })
})

// ── Click navigation ──────────────────────────────────────────────

describe('QuickWinsMatrix — click navigates to opportunity card', () => {
    /**
     * Hover-only pulses must NOT scroll (P1b regression). Clicking a
     * dot is the user's explicit "take me there" signal and DOES scroll
     * the matching opportunity card into view.
     */

    it('clicking an in-plot dot imperatively scrolls the matching opportunity card into view', () => {
        const scrollSpy = vi.spyOn(Element.prototype, 'scrollIntoView')
        render(
            <>
                <QuickWinsMatrix
                    opportunities={[
                        make({
                            title: 'First',
                            investment_value_usd: 100_000,
                            roi_estimate_pct: 150,
                        }),
                        make({
                            title: 'Second',
                            investment_value_usd: 200_000,
                            roi_estimate_pct: 50,
                        }),
                    ]}
                />
                <div data-testid="opportunity-card-1">Second opp card</div>
            </>
        )
        scrollSpy.mockClear()

        fireEvent.click(screen.getByTestId('quick-wins-dot-1'))

        expect(scrollSpy).toHaveBeenCalledWith({ behavior: 'smooth', block: 'nearest' })
        scrollSpy.mockRestore()
    })

    it('clicking an uncalibrated dot scrolls the matching opportunity card into view', () => {
        const scrollSpy = vi.spyOn(Element.prototype, 'scrollIntoView')
        render(
            <>
                <QuickWinsMatrix
                    opportunities={[make({ title: 'A', investment_value_usd: null, roi_estimate_pct: null })]}
                />
                <div data-testid="opportunity-card-0">A card</div>
            </>
        )
        scrollSpy.mockClear()

        fireEvent.click(screen.getByTestId('quick-wins-uncalibrated-dot-0'))

        expect(scrollSpy).toHaveBeenCalledWith({ behavior: 'smooth', block: 'nearest' })
        scrollSpy.mockRestore()
    })

    it('hovering a dot does NOT scroll (hover pulses only)', () => {
        const scrollSpy = vi.spyOn(Element.prototype, 'scrollIntoView')
        render(
            <QuickWinsMatrix
                opportunities={[make({ investment_value_usd: 100_000, roi_estimate_pct: 150 })]}
            />
        )
        scrollSpy.mockClear()

        fireEvent.mouseEnter(screen.getByTestId('quick-wins-dot-0'))

        expect(scrollSpy).not.toHaveBeenCalled()
        scrollSpy.mockRestore()
    })
})

// ── Cluster pin (>CLUSTER_THRESHOLD dots in a quadrant) ──────────

describe('QuickWinsMatrix — cluster pin', () => {
    /**
     * Build CLUSTER_THRESHOLD + 1 opportunities at identical coords so
     * they all land in the same quadrant and trigger the cluster
     * collapse.
     *
     * NOTE: when every dot shares the same (x, y), the per-scan median
     * equals that same coordinate, so every dot lands ON the median
     * split lines. ``quadrantFor`` routes on-median dots to the
     * right + bottom halves (``deprioritise``). The cluster therefore
     * forms in the ``deprioritise`` corner, not ``quick-wins``. See
     * the quickWinsMatrixLayout unit test "treats dots on the split
     * lines as belonging to the right/bottom halves" for the
     * canonical rule.
     */
    const TARGET_QUADRANT = 'deprioritise' as const

    function manyOppsInOneQuadrant(count: number): Opportunity[] {
        return Array.from({ length: count }, (_, i) =>
            make({
                title: `Opp ${i}`,
                investment_value_usd: 20_000,
                roi_estimate_pct: 250,
            })
        )
    }

    it('renders a cluster pin instead of individual dots when a quadrant exceeds the threshold', () => {
        const opps = manyOppsInOneQuadrant(CLUSTER_THRESHOLD + 1)
        render(<QuickWinsMatrix opportunities={opps} />)
        // No individual dots in the collapsed quadrant.
        expect(screen.queryByTestId('quick-wins-dot-0')).toBeNull()
        // Cluster pin is rendered.
        expect(screen.getByTestId(`quick-wins-cluster-${TARGET_QUADRANT}`)).toBeInTheDocument()
    })

    /**
     * Helper to click the cluster pin. The pin's outer ``<g>`` carries
     * the testid (so the click target is stable), but the click handler
     * is on the inner ``<g role="button">`` child — jsdom fires the
     * synthetic click on the targeted element only and the event won't
     * bubble up to a parent without an explicit listener, so we resolve
     * to the inner button by its ``aria-label`` (which scopes it past
     * the popover entry buttons that also render with ``role="button"``
     * once the popover is open).
     */
    function clickClusterPin(): void {
        const pin = screen.getByTestId(`quick-wins-cluster-${TARGET_QUADRANT}`)
        fireEvent.click(within(pin).getByRole('button', { name: /opportunities in/i }))
    }

    it('clicking the cluster pin opens a popover listing every opportunity in the quadrant', () => {
        const count = CLUSTER_THRESHOLD + 1
        const opps = manyOppsInOneQuadrant(count)
        render(<QuickWinsMatrix opportunities={opps} />)

        clickClusterPin()

        const popover = screen.getByTestId(`quick-wins-cluster-popover-${TARGET_QUADRANT}`)
        for (let i = 0; i < count; i += 1) {
            expect(within(popover).getByText(`Opp ${i}`)).toBeInTheDocument()
        }
    })

    it('clicking a popover entry dispatches that opportunity highlight and closes the popover', () => {
        const count = CLUSTER_THRESHOLD + 1
        const opps = manyOppsInOneQuadrant(count)
        render(
            <OpportunityHoverProvider>
                <QuickWinsMatrix opportunities={opps} />
                <HoverProbe />
                <div data-testid="opportunity-card-3">Opp 3 card</div>
            </OpportunityHoverProvider>
        )

        clickClusterPin()
        fireEvent.click(screen.getByTestId(`quick-wins-cluster-item-${TARGET_QUADRANT}-3`))

        expect(screen.getByTestId('hover-probe').getAttribute('data-indices')).toBe('3')
        expect(screen.queryByTestId(`quick-wins-cluster-popover-${TARGET_QUADRANT}`)).toBeNull()
    })

    it('clicking a popover entry scrolls the matching opportunity card into view', () => {
        const scrollSpy = vi.spyOn(Element.prototype, 'scrollIntoView')
        const count = CLUSTER_THRESHOLD + 1
        const opps = manyOppsInOneQuadrant(count)
        render(
            <>
                <QuickWinsMatrix opportunities={opps} />
                <div data-testid="opportunity-card-2">Opp 2 card</div>
            </>
        )
        clickClusterPin()
        scrollSpy.mockClear()

        fireEvent.click(screen.getByTestId(`quick-wins-cluster-item-${TARGET_QUADRANT}-2`))

        expect(scrollSpy).toHaveBeenCalledWith({ behavior: 'smooth', block: 'nearest' })
        scrollSpy.mockRestore()
    })

    it('toggles the popover closed when the cluster pin is clicked a second time', () => {
        const count = CLUSTER_THRESHOLD + 1
        const opps = manyOppsInOneQuadrant(count)
        render(<QuickWinsMatrix opportunities={opps} />)

        clickClusterPin()
        expect(screen.getByTestId(`quick-wins-cluster-popover-${TARGET_QUADRANT}`)).toBeInTheDocument()
        clickClusterPin()
        expect(screen.queryByTestId(`quick-wins-cluster-popover-${TARGET_QUADRANT}`)).toBeNull()
    })

    it('closes the popover on Escape keypress on the cluster pin', () => {
        const count = CLUSTER_THRESHOLD + 1
        const opps = manyOppsInOneQuadrant(count)
        render(<QuickWinsMatrix opportunities={opps} />)

        const pin = screen.getByTestId(`quick-wins-cluster-${TARGET_QUADRANT}`)
        // The keyboard handler is on the inner <g role="button"> child.
        // Disambiguate by aria-label since the popover (once open)
        // also contains buttons with ``role="button"``.
        const button = within(pin).getByRole('button', { name: /opportunities in/i })
        fireEvent.click(button)
        fireEvent.keyDown(button, { key: 'Escape' })
        expect(screen.queryByTestId(`quick-wins-cluster-popover-${TARGET_QUADRANT}`)).toBeNull()
    })

    it('keeps individual dots when a quadrant has exactly CLUSTER_THRESHOLD opportunities (boundary)', () => {
        const opps = manyOppsInOneQuadrant(CLUSTER_THRESHOLD)
        render(<QuickWinsMatrix opportunities={opps} />)
        // No cluster pin — the threshold is strictly greater-than.
        expect(screen.queryByTestId(`quick-wins-cluster-${TARGET_QUADRANT}`)).toBeNull()
        // Every dot is rendered individually.
        for (let i = 0; i < CLUSTER_THRESHOLD; i += 1) {
            expect(screen.getByTestId(`quick-wins-dot-${i}`)).toBeInTheDocument()
        }
    })
})
