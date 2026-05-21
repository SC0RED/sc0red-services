import { render, screen, within } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import PrintQuickWinsMatrix from '@/components/print/PrintQuickWinsMatrix'
import { sortOpportunities, type OpportunityWithIndex } from '@/lib/pdf/sortOpportunities'
import type { Opportunity } from '@/lib/types/api'
import { CLUSTER_THRESHOLD } from '@/lib/utils/quickWinsMatrixLayout'

/**
 * Tests for the print variant of the ROI × Investment matrix
 * (Phase 14 path B). The print component renders the same SVG
 * scatter plot as the screen variant but with no event handlers
 * and a numbered legend beneath the plot mapping #N → opportunity
 * title so paper readers can connect dots to opportunities without
 * hovering.
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

// ── Structural rendering ──────────────────────────────────────────

describe('PrintQuickWinsMatrix — structural rendering', () => {
    it('renders the section heading "ROI × Investment Matrix"', () => {
        renderWith([])
        expect(screen.getByRole('heading', { name: /ROI .{1,3} Investment Matrix/i })).toBeInTheDocument()
    })

    it('renders the SVG plot with quadrant corner labels', () => {
        renderWith([])
        expect(screen.getByTestId('print-quick-wins-matrix-svg')).toBeInTheDocument()
        expect(screen.getByTestId('print-quick-wins-quadrant-label-quick-wins')).toHaveTextContent(
            /QUICK WINS/i
        )
        expect(screen.getByTestId('print-quick-wins-quadrant-label-strategic-bets')).toHaveTextContent(
            /STRATEGIC BETS/i
        )
        expect(screen.getByTestId('print-quick-wins-quadrant-label-fill-ins')).toHaveTextContent(/FILL-INS/i)
        expect(screen.getByTestId('print-quick-wins-quadrant-label-deprioritise')).toHaveTextContent(
            /DEPRIORITISE/i
        )
    })

    it('renders log-scale X-axis ticks ($10K → $10M) and linear Y-axis ticks (0% → 300%)', () => {
        renderWith([])
        const svg = screen.getByTestId('print-quick-wins-matrix-svg')
        expect(within(svg).getByText('$10K')).toBeInTheDocument()
        expect(within(svg).getByText('$10M')).toBeInTheDocument()
        expect(within(svg).getByText('0%')).toBeInTheDocument()
        expect(within(svg).getByText('300%')).toBeInTheDocument()
    })
})

// ── Dot rendering + legend ────────────────────────────────────────

describe('PrintQuickWinsMatrix — dots + legend', () => {
    it('renders an in-plot dot for opportunities with both numeric axes populated', () => {
        const opps = [
            make({
                title: 'Sized opp',
                investment_value_usd: 100_000,
                roi_estimate_pct: 150,
            }),
        ]
        renderWith(opps)
        expect(screen.getByTestId('print-quick-wins-dot-0')).toBeInTheDocument()
    })

    it('labels each in-plot dot with its printed-index reference', () => {
        const opps = [
            make({
                title: 'Sized opp',
                investment_value_usd: 100_000,
                roi_estimate_pct: 150,
            }),
        ]
        renderWith(opps)
        const dot = screen.getByTestId('print-quick-wins-dot-0')
        // First (and only) opportunity gets printedIndex 1.
        expect(dot.textContent).toContain('#1')
    })

    it('renders the plotted-opportunity legend with #N → title entries', () => {
        const opps = [
            make({
                title: 'Roll out signature beverage',
                investment_value_usd: 100_000,
                roi_estimate_pct: 150,
            }),
        ]
        renderWith(opps)
        const legend = screen.getByTestId('print-quick-wins-legend')
        expect(legend.textContent).toMatch(/#1 Roll out signature beverage/)
    })

    it('renders the uncalibrated legend for opportunities missing either numeric axis', () => {
        const opps = [
            make({
                title: 'Unsized opp',
                investment_value_usd: null,
                roi_estimate_pct: null,
            }),
        ]
        renderWith(opps)
        const uncalibrated = screen.getByTestId('print-quick-wins-uncalibrated')
        expect(uncalibrated.textContent).toMatch(/#1 Unsized opp/)
    })

    it('lists plotted and uncalibrated opportunities in separate legend sections', () => {
        const opps = [
            make({
                title: 'Plotted',
                investment_value_usd: 100_000,
                roi_estimate_pct: 150,
            }),
            make({
                title: 'Unsized',
                investment_value_usd: null,
                roi_estimate_pct: null,
            }),
        ]
        renderWith(opps)
        const legend = screen.getByTestId('print-quick-wins-legend')
        const uncalibrated = screen.getByTestId('print-quick-wins-uncalibrated')
        // The plotted heading lives in the legend but outside the
        // uncalibrated subsection.
        expect(legend.textContent).toContain('Plotted')
        expect(uncalibrated.textContent).toContain('Unsized')
        expect(uncalibrated.textContent).not.toContain('Plotted')
    })

    it('renders a clamp caret on dots whose ROI exceeded the visual cap', () => {
        const opps = [
            make({
                title: 'High ROI',
                investment_value_usd: 100_000,
                roi_estimate_pct: 450,
            }),
        ]
        renderWith(opps)
        const dot = screen.getByTestId('print-quick-wins-dot-0')
        expect(dot.textContent).toContain('↑')
    })

    it('renders a cluster pin when a quadrant exceeds the cluster threshold', () => {
        // Identical coords land all dots on the median split, which
        // routes to the bottom-right quadrant per quadrantFor's
        // ``< splitX`` / ``< splitY`` rule.
        const opps = Array.from({ length: CLUSTER_THRESHOLD + 1 }, (_, i) =>
            make({
                title: `Opp ${i}`,
                investment_value_usd: 20_000,
                roi_estimate_pct: 250,
            })
        )
        renderWith(opps)
        expect(screen.getByTestId('print-quick-wins-cluster-deprioritise')).toBeInTheDocument()
        // No individual dots survive in the collapsed quadrant.
        expect(screen.queryByTestId('print-quick-wins-dot-0')).toBeNull()
        // Every member opportunity appears in the legend so the cluster
        // is still resolvable on paper.
        const legend = screen.getByTestId('print-quick-wins-legend')
        for (let i = 0; i < CLUSTER_THRESHOLD + 1; i += 1) {
            expect(legend.textContent).toContain(`Opp ${i}`)
        }
    })
})

// ── Interactivity stripped ────────────────────────────────────────

describe('PrintQuickWinsMatrix — interactivity stripped', () => {
    it('renders no <button> elements in the print DOM (no hover, no popover)', () => {
        const opps = Array.from({ length: CLUSTER_THRESHOLD + 1 }, (_, i) =>
            make({
                title: `Opp ${i}`,
                investment_value_usd: 100_000,
                roi_estimate_pct: 150,
            })
        )
        const { container } = renderWith(opps)
        expect(container.querySelectorAll('button').length).toBe(0)
    })

    it("does not render the screen variant's popover or hover testids", () => {
        const opps = Array.from({ length: CLUSTER_THRESHOLD + 1 }, (_, i) =>
            make({
                title: `Opp ${i}`,
                investment_value_usd: 20_000,
                roi_estimate_pct: 250,
            })
        )
        renderWith(opps)
        // Screen-only testids must not appear.
        expect(screen.queryByTestId('quick-wins-cluster-popover-deprioritise')).toBeNull()
        expect(screen.queryByTestId('quick-wins-uncalibrated-strip')).toBeNull()
    })
})
