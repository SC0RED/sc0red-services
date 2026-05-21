import type { CSSProperties } from 'react'

import type { OpportunityWithIndex } from '@/lib/pdf/sortOpportunities'
import type { buildQuickWinsMatrixLayout } from '@/lib/utils/quickWinsMatrixLayout'

/**
 * Numbered legend rendered beneath the print scatter plot. Lists every
 * opportunity that appears in the plot or a cluster (left column) and
 * every uncalibrated opportunity (right column) with its printed-index
 * reference so paper readers can resolve a dot's ``#N`` label without
 * hovering.
 *
 * Returns ``null`` when there are no opportunities to list at all —
 * the wrapping ``PrintQuickWinsMatrix`` already gates on a non-empty
 * sorted-opportunities array, but the legend defends against the
 * edge case where every entry got filtered out.
 */
export default function PrintLegend({
    layout,
    sortedOpportunities,
}: {
    layout: ReturnType<typeof buildQuickWinsMatrixLayout>
    sortedOpportunities: OpportunityWithIndex[]
}) {
    // Build a single, deterministic, printed-index-ordered list of
    // every opportunity that appears in the plot or a cluster, plus
    // the uncalibrated strip. Each entry shows ``#N — Title`` so the
    // paper reader can resolve a dot's printed index without hovering.
    const plottedIndices = new Set<number>()
    for (const dot of layout.inPlot) plottedIndices.add(dot.opportunityIndex)
    for (const pin of layout.clusterPins) {
        for (const i of pin.opportunityIndices) plottedIndices.add(i)
    }
    const uncalibratedIndices = layout.uncalibrated.map((u) => u.opportunityIndex)

    const plottedEntries = sortedOpportunities.filter((entry) => plottedIndices.has(entry.originalIndex))
    const uncalibratedEntries = sortedOpportunities.filter((entry) =>
        uncalibratedIndices.includes(entry.originalIndex)
    )

    if (plottedEntries.length === 0 && uncalibratedEntries.length === 0) return null

    return (
        <div data-testid="print-quick-wins-legend" style={legendContainerStyle}>
            {plottedEntries.length > 0 ? (
                <div>
                    <div style={legendHeadingStyle}>Plotted opportunities</div>
                    <ul style={legendListStyle}>
                        {plottedEntries.map((entry) => (
                            <li key={entry.originalIndex} style={legendItemStyle}>
                                #{entry.printedIndex} {entry.opportunity.title}
                            </li>
                        ))}
                    </ul>
                </div>
            ) : null}
            {uncalibratedEntries.length > 0 ? (
                <div data-testid="print-quick-wins-uncalibrated">
                    <div style={legendHeadingStyle}>Opportunities without ROI / investment estimates</div>
                    <ul style={legendListStyle}>
                        {uncalibratedEntries.map((entry) => (
                            <li key={entry.originalIndex} style={legendItemStyle}>
                                #{entry.printedIndex} {entry.opportunity.title}
                            </li>
                        ))}
                    </ul>
                </div>
            ) : null}
        </div>
    )
}

// ── styles ────────────────────────────────────────────────────────

const legendContainerStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '14px',
    marginTop: '14px',
}

const legendHeadingStyle: CSSProperties = {
    fontSize: '0.7rem',
    color: 'var(--text-tertiary)',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    marginBottom: '4px',
}

const legendListStyle: CSSProperties = {
    listStyle: 'none',
    margin: 0,
    padding: 0,
    fontSize: '0.7rem',
    color: 'var(--text-secondary)',
    lineHeight: 1.4,
}

const legendItemStyle: CSSProperties = {
    margin: 0,
}
