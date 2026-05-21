import type { CSSProperties } from 'react'

import PrintLegend from '@/components/print/quick-wins-matrix/PrintLegend'
import PrintScatterPlot from '@/components/print/quick-wins-matrix/PrintScatterPlot'
import type { OpportunityWithIndex } from '@/lib/pdf/sortOpportunities'
import type { Opportunity } from '@/lib/types/api'
import { buildQuickWinsMatrixLayout } from '@/lib/utils/quickWinsMatrixLayout'

interface PrintQuickWinsMatrixProps {
    /** Same sorted-with-original-index list used elsewhere in the PDF.
     *  Required so each dot can render its printed-index reference in
     *  the legend below the plot. */
    sortedOpportunities: OpportunityWithIndex[]
}

/**
 * Print-only ROI × Investment Matrix (Phase 14 path B).
 *
 * Static parallel to the screen ``QuickWinsMatrix``: same SVG scatter
 * plot on log-scale investment (X) × linear ROI (Y), same quadrant
 * labels at the corners, same uncalibrated strip for opportunities
 * the AI couldn't size. No event handlers, no popovers.
 *
 * Paper readers can't hover, so each dot also carries a printed-index
 * label (``#N``) and a legend below the chart maps ``#N`` → opportunity
 * title. Cluster pins survive as a "+N" overlay; their member
 * opportunities show up in the legend instead of a popover.
 *
 * Sits inside ``PrintReport.tsx`` between the opportunity list and the
 * back cover, gated on ``opportunities.length >= 1``.
 *
 * The SVG plot and the numbered legend live in ``quick-wins-matrix/``
 * to keep this file under the 360-line frontend cap.
 */
export default function PrintQuickWinsMatrix({ sortedOpportunities }: PrintQuickWinsMatrixProps) {
    // The matrix layout helper expects ``Opportunity[]`` in original-
    // index order — every dot's ``opportunityIndex`` points into that
    // array. ``sortedOpportunities`` is print-display sort (by impact)
    // layered on top, so reverse the sort first.
    const opportunities = sortedOpportunities
        .slice()
        .sort((a, b) => a.originalIndex - b.originalIndex)
        .map((entry) => entry.opportunity) as Opportunity[]

    const PLOT_WIDTH = 540
    const PLOT_HEIGHT = 320
    const layout = buildQuickWinsMatrixLayout(opportunities, PLOT_WIDTH, PLOT_HEIGHT)

    return (
        <section className="print-section print-section--break-before print-quick-wins-matrix">
            <h2>ROI × Investment Matrix</h2>

            <p style={leadStyle}>
                Each opportunity is plotted by investment cost (horizontal, log scale) and ROI (vertical).
                Opportunities the AI couldn&rsquo;t size land in the uncalibrated strip beneath the plot.
            </p>

            <PrintScatterPlot
                plotWidth={PLOT_WIDTH}
                plotHeight={PLOT_HEIGHT}
                layout={layout}
                sortedOpportunities={sortedOpportunities}
            />

            <PrintLegend layout={layout} sortedOpportunities={sortedOpportunities} />
        </section>
    )
}

// ── styles ────────────────────────────────────────────────────────

const leadStyle: CSSProperties = {
    margin: '0 0 12px',
    fontSize: '0.85rem',
    color: 'var(--text-secondary)',
    lineHeight: 1.5,
}
