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
 * The label-overlap follow-up replaced inline title text on each dot
 * with a numbered badge (``#N``) and a sidebar
 * ``OpportunityLegendColumn`` mapping ``#N`` → full title. See
 * ``QuickWinsMatrix.tsx`` for the design rationale.
 *
 * Test ids exposed by the component:
 *
 *   quick-wins-matrix                   — outer container
 *   quick-wins-matrix-svg               — the SVG plot
 *   quick-wins-matrix-median-caveat     — relative-split caveat copy
 *   quick-wins-matrix-lever-legend      — lever color legend above the chart
 *   quick-wins-dot-{n}                  — individual in-plot dot
 *   quick-wins-dot-outer-{n}            — donut outer ring (lever-coloured fill)
 *   quick-wins-dot-inner-{n}            — donut inner disc (neutral surface)
 *   quick-wins-dot-number-{n}           — numbered badge text on the dot
 *   quick-wins-dot-ring-{n}             — hover/focus highlight ring
 *   quick-wins-cluster-{quadrant}       — cluster pin (when > threshold)
 *   quick-wins-cluster-popover-{quad}   — cluster popover (when open)
 *   quick-wins-cluster-item-{q}-{n}     — popover entry
 *   quick-wins-uncalibrated-strip       — footer strip (when non-empty)
 *   quick-wins-uncalibrated-dot-{n}     — uncalibrated dot
 *   quick-wins-quadrant-label-{quad}    — quadrant label (outer margin)
 *   quick-wins-legend-column            — sidebar legend root
 *   quick-wins-legend-group-{quadrant}  — per-quadrant legend section
 *   quick-wins-legend-group-uncalibrated — legend section for uncalibrated entries
 *   quick-wins-legend-entry-{n}         — sidebar legend button per opportunity
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
        // aria-label includes the badge number so screen-reader users
        // can correlate the spoken label to the on-chart "#N" badge
        // and to the matching legend-column entry (which uses the
        // same "Highlight opportunity {N}: {title}" format).
        expect(dot).toHaveAttribute('aria-label', 'Highlight opportunity 1: Cut SaaS sprawl')
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

    it('renders a 1-based numbered badge inside the dot instead of an inline title label', () => {
        // The badge replaces the previous inline title text. The full
        // title moves to the sidebar legend so two dots in the same
        // horizontal band can no longer collide on the chart.
        render(
            <QuickWinsMatrix
                opportunities={[
                    make({
                        title: 'Cut SaaS sprawl',
                        investment_value_usd: 100_000,
                        roi_estimate_pct: 150,
                    }),
                    make({
                        title: 'Sign warehouse lease',
                        investment_value_usd: 200_000,
                        roi_estimate_pct: 110,
                    }),
                ]}
            />
        )
        // The previous inline-title testid must no longer exist.
        expect(screen.queryByTestId('quick-wins-dot-label-0')).toBeNull()
        // 1-based numbering: index 0 → "1", index 1 → "2".
        expect(screen.getByTestId('quick-wins-dot-number-0')).toHaveTextContent('1')
        expect(screen.getByTestId('quick-wins-dot-number-1')).toHaveTextContent('2')
    })

    it('keeps the full title in the SVG <title> tooltip + aria-label for screen readers and hover-tooltip users', () => {
        // Long title — under the old design this got truncated to
        // 22 chars; the new design dropped truncation entirely because
        // the inline label is gone.
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
        const dot = screen.getByTestId('quick-wins-dot-0')
        // Title tooltip carries #N + full title + lever.
        expect(dot.querySelector('title')?.textContent).toBe(
            '#1 Deploy AI churn prediction model end-to-end (Revenue Side)'
        )
        // aria-label still uses the full unabridged title so screen
        // readers announce the same content as sighted users see in
        // the legend column.
        expect(dot).toHaveAttribute(
            'aria-label',
            'Highlight opportunity 1: Deploy AI churn prediction model end-to-end'
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

    it('renders the dot as a donut — lever-coloured outer ring + neutral inner disc + lever-coloured number', () => {
        // Donut shape exists to fix WCAG contrast on the numbered badge:
        // the previous solid-fill dot rendered white text on a saturated
        // lever colour and failed contrast across all three levers (see
        // design.md decision 9). The donut puts the number on a neutral
        // interior token so contrast clears in both themes.
        render(
            <QuickWinsMatrix
                opportunities={[
                    make({
                        value_lever: 'Revenue Side',
                        investment_value_usd: 100_000,
                        roi_estimate_pct: 150,
                    }),
                ]}
            />
        )
        const outer = screen.getByTestId('quick-wins-dot-outer-0')
        const inner = screen.getByTestId('quick-wins-dot-inner-0')
        const number = screen.getByTestId('quick-wins-dot-number-0')

        expect(outer).toHaveAttribute('fill', 'var(--lever-revenue)')
        expect(inner).toHaveAttribute('fill', 'var(--bg-surface-3)')
        // Number fill matches the lever colour (NOT white) so it
        // contrasts against the neutral inner disc, not the saturated
        // outer ring. ``<text>`` receives ``fill`` via inline style,
        // not the HTML attribute, so check the rendered style string.
        expect(number.getAttribute('style') ?? '').toContain('fill: var(--lever-revenue)')
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

// ── Lever color legend + median caveat ────────────────────────────

describe('QuickWinsMatrix — lever colour legend + median caveat', () => {
    it('renders the lever colour legend above the chart with matrix-specific copy', () => {
        render(<QuickWinsMatrix opportunities={[]} />)
        const legend = screen.getByTestId('quick-wins-matrix-lever-legend')
        // The matrix sentence is distinct from the strategy-map /
        // EBITDA / value-chain sentence: the dot IS the opportunity
        // (not something that targets one), so the noun structure
        // flips.
        expect(legend).toHaveTextContent(/each dot is an AI opportunity, coloured by value lever\./i)
        // All three lever labels appear in the legend.
        expect(legend).toHaveTextContent('Revenue Side')
        expect(legend).toHaveTextContent('Cost Side')
        expect(legend).toHaveTextContent('Both')
    })

    it('shows a caveat clarifying that the quadrant split is relative to this analysis', () => {
        render(<QuickWinsMatrix opportunities={[]} />)
        const caveat = screen.getByTestId('quick-wins-matrix-median-caveat')
        expect(caveat).toHaveTextContent(/median investment and median ROI of this analysis/i)
        expect(caveat).toHaveTextContent(/not fixed industry thresholds/i)
    })
})

// ── Sidebar legend column ─────────────────────────────────────────

describe('QuickWinsMatrix — sidebar legend column', () => {
    it('renders one legend entry per in-plot opportunity, grouped by quadrant', () => {
        render(
            <QuickWinsMatrix
                opportunities={[
                    // Lands in fill-ins after median-split (low ROI, low investment relative to set)
                    make({ title: 'Patch invoicing', investment_value_usd: 15_000, roi_estimate_pct: 30 }),
                    // Lands in strategic-bets (high investment, high ROI)
                    make({
                        title: 'Roll out platform',
                        investment_value_usd: 5_000_000,
                        roi_estimate_pct: 250,
                    }),
                ]}
            />
        )
        expect(screen.getByTestId('quick-wins-legend-column')).toBeInTheDocument()
        // One entry button per opportunity, identified by the same
        // 1-based numbering scheme used on the dot badges.
        const entry0 = screen.getByTestId('quick-wins-legend-entry-0')
        const entry1 = screen.getByTestId('quick-wins-legend-entry-1')
        expect(entry0).toHaveTextContent('Patch invoicing')
        expect(entry1).toHaveTextContent('Roll out platform')
        // 1-based number prefix on each entry.
        expect(entry0).toHaveTextContent('1')
        expect(entry1).toHaveTextContent('2')
    })

    it('routes uncalibrated opportunities into a dedicated legend section', () => {
        render(
            <QuickWinsMatrix
                opportunities={[
                    make({
                        title: 'Mystery opp',
                        investment_value_usd: null,
                        roi_estimate_pct: null,
                    }),
                ]}
            />
        )
        const group = screen.getByTestId('quick-wins-legend-group-uncalibrated')
        expect(group).toHaveTextContent('Mystery opp')
        expect(group).toHaveTextContent(/uncalibrated/i)
    })

    it('hovering a legend entry highlights the matching opportunity via the shared provider', () => {
        render(
            <OpportunityHoverProvider>
                <QuickWinsMatrix
                    opportunities={[
                        make({
                            title: 'Cut SaaS sprawl',
                            investment_value_usd: 100_000,
                            roi_estimate_pct: 150,
                        }),
                    ]}
                />
                <HoverProbe />
            </OpportunityHoverProvider>
        )
        const entry = screen.getByTestId('quick-wins-legend-entry-0')
        const probe = () => screen.getByTestId('hover-probe').getAttribute('data-indices')

        expect(probe()).toBe('')
        fireEvent.mouseEnter(entry)
        expect(probe()).toBe('0')
        fireEvent.mouseLeave(entry)
        expect(probe()).toBe('')
    })

    it('clicking a legend entry scrolls the matching opportunity card into view', () => {
        const scrollSpy = vi.spyOn(Element.prototype, 'scrollIntoView')
        render(
            <>
                <QuickWinsMatrix
                    opportunities={[
                        make({
                            title: 'Cut SaaS sprawl',
                            investment_value_usd: 100_000,
                            roi_estimate_pct: 150,
                        }),
                    ]}
                />
                <div data-testid="opportunity-card-0">Card</div>
            </>
        )
        scrollSpy.mockClear()

        fireEvent.click(screen.getByTestId('quick-wins-legend-entry-0'))

        expect(scrollSpy).toHaveBeenCalledWith({ behavior: 'smooth', block: 'nearest' })
        scrollSpy.mockRestore()
    })

    it('includes opportunities that landed inside a cluster pin in the legend column', () => {
        // When a quadrant collapses into a cluster pin, the individual
        // dot testids disappear from the chart — but the legend column
        // must still list every collapsed opportunity so the reader
        // never loses access to a title.
        const count = CLUSTER_THRESHOLD + 1
        const opps = Array.from({ length: count }, (_, i) =>
            make({
                title: `Cluster opp ${i}`,
                investment_value_usd: 20_000,
                roi_estimate_pct: 250,
            })
        )
        render(<QuickWinsMatrix opportunities={opps} />)
        for (let i = 0; i < count; i += 1) {
            expect(screen.getByTestId(`quick-wins-legend-entry-${i}`)).toBeInTheDocument()
        }
    })
})

// ── Hover focus ring ──────────────────────────────────────────────

describe('QuickWinsMatrix — hover focus ring', () => {
    it('marks the focus ring inactive when no dot is hovered', () => {
        render(
            <QuickWinsMatrix
                opportunities={[make({ investment_value_usd: 100_000, roi_estimate_pct: 150 })]}
            />
        )
        // ``data-active`` is the semantic contract — assert on it
        // (not on opacity / visibility / display) so the test survives
        // future visual treatment changes.
        const ring = screen.getByTestId('quick-wins-dot-ring-0')
        expect(ring.getAttribute('data-active')).toBe('false')
    })

    it('marks the focus ring active when the dot is hovered (via the shared provider)', () => {
        render(
            <OpportunityHoverProvider>
                <QuickWinsMatrix
                    opportunities={[make({ investment_value_usd: 100_000, roi_estimate_pct: 150 })]}
                />
            </OpportunityHoverProvider>
        )
        const dot = screen.getByTestId('quick-wins-dot-0')
        fireEvent.mouseEnter(dot)
        const ring = screen.getByTestId('quick-wins-dot-ring-0')
        expect(ring.getAttribute('data-active')).toBe('true')
    })
})
