'use client'

import { type CSSProperties } from 'react'

import AnalysisLegend from '@/components/analysis/AnalysisLegend'
import OpportunityLegendColumn from '@/components/analysis/quick-wins-matrix/OpportunityLegendColumn'
import ScatterPlot from '@/components/analysis/quick-wins-matrix/ScatterPlot'
import UncalibratedStrip from '@/components/analysis/quick-wins-matrix/UncalibratedStrip'
import type { Opportunity } from '@/lib/types/api'
import { buildQuickWinsMatrixLayout } from '@/lib/utils/quickWinsMatrixLayout'

interface QuickWinsMatrixProps {
    opportunities: Opportunity[]
}

/**
 * ROI × Investment Matrix — true 2D scatter plot of every opportunity
 * the AI was able to size on both numeric axes. Opportunities with a
 * missing axis route to a separate uncalibrated strip beneath the
 * plot.
 *
 * Design D8 of ``redesign-analysis-visuals`` shipped the scatter plot;
 * the follow-up ``fix/quick-wins-matrix-label-overlap`` change replaced
 * the inline title text next to each dot — which collided as soon as
 * two opportunities landed in the same horizontal band — with three
 * compounding affordances:
 *
 *   1. Each dot carries a numbered badge (``#N``) instead of a 22-char
 *      truncated title. Badge stays inside the dot, so two dots can
 *      sit shoulder-to-shoulder without label overlap.
 *   2. A sidebar ``OpportunityLegendColumn`` maps ``#N`` → full title,
 *      grouped by quadrant. The full title is always visible without
 *      truncation or hover.
 *   3. The lever-colour vocabulary is taught via an ``AnalysisLegend``
 *      directly above the chart so a reader landing here from the
 *      executive summary doesn't have to scroll up to recall what
 *      green / blue / mixed mean.
 *
 * Quadrant labels live in the outer chart margin (above the top edge
 * for Quick Wins / Strategic Bets, below for Fill-Ins / Deprioritise)
 * so they never collide with dots near the corners — which is exactly
 * where the "Quick Wins" corner attracts them by design.
 *
 * Quadrant split lines are drawn at the MEDIAN investment + median
 * ROI of the in-plot subset (per-scan, not fixed thresholds), so the
 * quadrant labels stay meaningful regardless of the analysis's
 * absolute scale. A subtitle calls out the relative nature of the
 * split so readers don't read "Quick Wins" as an absolute claim.
 *
 * **Numbering convention.** Screen-variant ``#N`` is the 1-based badge
 * label (array index + 1). The opportunity card below the chart uses
 * the 0-based array index in its testid — so the badge ``#N`` on the
 * chart corresponds to ``data-testid="opportunity-card-{N - 1}"``. The
 * click handlers in ``ScatterDot`` and ``OpportunityLegendColumn`` keep
 * track of the 0-based index internally and target the correct testid;
 * the 1-based label is purely a display affordance because "#1" reads
 * better than "#0" for the first opportunity.
 *
 * The print variant (``PrintQuickWinsMatrix``) instead uses the
 * impact-sorted ``printedIndex`` because paper readers scan by impact,
 * not array order. Screen ``#3`` and print ``#3`` can therefore refer
 * to different opportunities for the same analysis — that is deliberate
 * and documented in both component headers.
 *
 * The chart surface, sidebar legend, lever colour legend, and
 * uncalibrated strip each live in their own sub-component under
 * ``quick-wins-matrix/`` so this file stays a thin composition layer.
 */
export default function QuickWinsMatrix({ opportunities }: QuickWinsMatrixProps) {
    // Fixed plot dimensions in viewBox coordinate space. The wrapping
    // SVG uses ``preserveAspectRatio="xMidYMid meet"`` so the actual
    // rendered size scales to the container width while keeping the
    // aspect ratio fixed. Pixel coordinates from
    // ``buildQuickWinsMatrixLayout`` are in this same space — click
    // hit-testing works the same regardless of the rendered scale.
    const PLOT_WIDTH = 720
    const PLOT_HEIGHT = 420

    const layout = buildQuickWinsMatrixLayout(opportunities, PLOT_WIDTH, PLOT_HEIGHT)

    return (
        <div data-testid="quick-wins-matrix" style={containerStyle}>
            <p style={leadStyle}>
                Each opportunity is plotted by investment cost (horizontal, log scale) and ROI (vertical). The
                top-left quadrant carries the highest-leverage near-term plays; bottom-right are low-impact,
                slow-payoff — deprioritise unless context shifts. Opportunities the AI couldn&rsquo;t size
                land in the uncalibrated strip below.
            </p>
            <p data-testid="quick-wins-matrix-median-caveat" style={caveatStyle}>
                Quadrant split lines are drawn at the median investment and median ROI of this analysis, so
                the four quadrants are relative to this set — not fixed industry thresholds.
            </p>

            <AnalysisLegend tool="quick-wins-matrix" />

            <div style={chartAndLegendStyle}>
                <div style={chartColumnStyle}>
                    <ScatterPlot
                        plotWidth={PLOT_WIDTH}
                        plotHeight={PLOT_HEIGHT}
                        layout={layout}
                        opportunities={opportunities}
                    />
                </div>
                <OpportunityLegendColumn layout={layout} opportunities={opportunities} />
            </div>

            <UncalibratedStrip
                indices={layout.uncalibrated.map((u) => u.opportunityIndex)}
                opportunities={opportunities}
            />
        </div>
    )
}

// ── styles ────────────────────────────────────────────────────────

const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
}

const leadStyle: CSSProperties = {
    margin: 0,
    fontSize: '0.875rem',
    color: 'var(--text-secondary)',
    lineHeight: 1.6,
}

const caveatStyle: CSSProperties = {
    margin: 0,
    fontSize: '0.75rem',
    color: 'var(--text-tertiary)',
    lineHeight: 1.5,
    fontStyle: 'italic',
}

/** Side-by-side grid for chart + sidebar legend on wide viewports. The
 *  ``minmax(0, …fr)`` shorthands stop the chart column from blowing
 *  out when the legend's longest title forces a wider intrinsic min,
 *  and keep the legend's ``text-overflow: ellipsis`` working. */
const chartAndLegendStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1.6fr) minmax(0, 1fr)',
    gap: '20px',
    alignItems: 'start',
}

const chartColumnStyle: CSSProperties = {
    minWidth: 0,
}
