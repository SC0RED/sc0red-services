import type { CSSProperties } from 'react'

import { findByOriginalIndex, type OpportunityWithIndex } from '@/lib/pdf/sortOpportunities'
import { LEVER_COLORS } from '@/lib/utils/leverColors'
import {
    INVESTMENT_MAX_USD,
    INVESTMENT_MIN_USD,
    QUADRANT_LABELS,
    ROI_MAX_PCT,
    ROI_MIN_PCT,
    buildQuickWinsMatrixLayout,
    formatInvestmentTick,
    projectInvestmentTickX,
    projectRoiTickY,
    type ClusterPin,
    type InPlotDot,
    type Quadrant,
} from '@/lib/utils/quickWinsMatrixLayout'

/**
 * Static SVG scatter plot for the print PDF — parallel to the screen
 * variant's ``ScatterPlot`` but with no event handlers. Each in-plot
 * dot carries its printed-index reference (``#N``) so paper readers
 * can resolve a dot to an opportunity via the ``PrintLegend`` below.
 */
export default function PrintScatterPlot({
    plotWidth,
    plotHeight,
    layout,
    sortedOpportunities,
}: {
    plotWidth: number
    plotHeight: number
    layout: ReturnType<typeof buildQuickWinsMatrixLayout>
    sortedOpportunities: OpportunityWithIndex[]
}) {
    const margin = { top: 12, right: 12, bottom: 44, left: 52 }
    const svgWidth = plotWidth + margin.left + margin.right
    const svgHeight = plotHeight + margin.top + margin.bottom

    const xTicks = [INVESTMENT_MIN_USD, 100_000, 1_000_000, INVESTMENT_MAX_USD]
    const yTicks = [ROI_MIN_PCT, 100, 200, ROI_MAX_PCT]

    return (
        <svg
            data-testid="print-quick-wins-matrix-svg"
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            preserveAspectRatio="xMidYMid meet"
            style={svgStyle}
        >
            <g transform={`translate(${margin.left}, ${margin.top})`}>
                <rect
                    x={0}
                    y={0}
                    width={plotWidth}
                    height={plotHeight}
                    fill="var(--bg-surface-2)"
                    stroke="var(--border-subtle)"
                    strokeWidth={1}
                />

                {/* Quadrant split lines (median-based, dashed) */}
                <line
                    x1={layout.investmentSplitX}
                    y1={0}
                    x2={layout.investmentSplitX}
                    y2={plotHeight}
                    stroke="var(--border-subtle)"
                    strokeWidth={1}
                    strokeDasharray="4 3"
                />
                <line
                    x1={0}
                    y1={layout.roiSplitY}
                    x2={plotWidth}
                    y2={layout.roiSplitY}
                    stroke="var(--border-subtle)"
                    strokeWidth={1}
                    strokeDasharray="4 3"
                />

                {/* Quadrant labels */}
                <PrintQuadrantLabel quadrant="quick-wins" x={6} y={16} textAnchor="start" />
                <PrintQuadrantLabel quadrant="strategic-bets" x={plotWidth - 6} y={16} textAnchor="end" />
                <PrintQuadrantLabel quadrant="fill-ins" x={6} y={plotHeight - 8} textAnchor="start" />
                <PrintQuadrantLabel
                    quadrant="deprioritise"
                    x={plotWidth - 6}
                    y={plotHeight - 8}
                    textAnchor="end"
                />

                {/* Dots + cluster pins */}
                {layout.inPlot.map((dot) => (
                    <PrintScatterDot
                        key={`dot-${dot.opportunityIndex}`}
                        dot={dot}
                        sortedOpportunities={sortedOpportunities}
                    />
                ))}
                {layout.clusterPins.map((pin) => (
                    <PrintClusterPin key={`cluster-${pin.quadrant}`} pin={pin} />
                ))}
            </g>

            {/* X axis ticks + title */}
            <g transform={`translate(${margin.left}, ${margin.top + plotHeight})`}>
                {xTicks.map((tick) => {
                    const x = projectInvestmentTickX(tick, plotWidth)
                    return (
                        <g key={`xtick-${tick}`} transform={`translate(${x}, 0)`}>
                            <line y1={0} y2={4} stroke="var(--text-tertiary)" />
                            <text y={16} textAnchor="middle" style={tickLabelStyle}>
                                {formatInvestmentTick(tick)}
                            </text>
                        </g>
                    )
                })}
                <text x={plotWidth / 2} y={36} textAnchor="middle" style={axisTitleStyle}>
                    Investment (USD, log scale)
                </text>
            </g>

            {/* Y axis ticks + title */}
            <g transform={`translate(${margin.left}, ${margin.top})`}>
                {yTicks.map((tick) => {
                    const y = projectRoiTickY(tick, plotHeight)
                    return (
                        <g key={`ytick-${tick}`} transform={`translate(0, ${y})`}>
                            <line x1={-4} x2={0} stroke="var(--text-tertiary)" />
                            <text x={-8} y={4} textAnchor="end" style={tickLabelStyle}>
                                {tick}%
                            </text>
                        </g>
                    )
                })}
                <text
                    transform={`translate(-40, ${plotHeight / 2}) rotate(-90)`}
                    textAnchor="middle"
                    style={axisTitleStyle}
                >
                    ROI (%)
                </text>
            </g>
        </svg>
    )
}

// ── Sub-components ────────────────────────────────────────────────

function PrintScatterDot({
    dot,
    sortedOpportunities,
}: {
    dot: InPlotDot
    sortedOpportunities: OpportunityWithIndex[]
}) {
    const entry = findByOriginalIndex(sortedOpportunities, dot.opportunityIndex)
    if (!entry) {
        // Defend against orphan opportunity indices. The screen variant
        // throws here because its hover provider relies on the array
        // being well-formed; the print path is static so we just skip
        // — a missing dot is less surprising on paper than a crash.
        return null
    }
    const lever = entry.opportunity.value_lever ?? 'Both'
    const color = LEVER_COLORS[lever] ?? 'var(--text-tertiary)'

    return (
        <g
            data-testid={`print-quick-wins-dot-${dot.opportunityIndex}`}
            transform={`translate(${dot.x}, ${dot.y})`}
        >
            <circle r={4} fill={color} stroke="var(--bg-surface)" strokeWidth={1} />
            {dot.clampedUp ? (
                <text x={0} y={-7} textAnchor="middle" style={clampCaretStyle} aria-hidden="true">
                    ↑
                </text>
            ) : null}
            <text x={6} y={4} style={dotIndexStyle}>
                #{entry.printedIndex}
            </text>
        </g>
    )
}

function PrintClusterPin({ pin }: { pin: ClusterPin }) {
    return (
        <g
            data-testid={`print-quick-wins-cluster-${pin.quadrant}`}
            transform={`translate(${pin.x}, ${pin.y})`}
        >
            <circle r={11} fill="var(--accent-blue)" stroke="var(--bg-surface)" strokeWidth={2} />
            <text textAnchor="middle" dy={3} style={clusterCountStyle}>
                +{pin.opportunityIndices.length}
            </text>
        </g>
    )
}

function PrintQuadrantLabel({
    quadrant,
    x,
    y,
    textAnchor,
}: {
    quadrant: Quadrant
    x: number
    y: number
    textAnchor: 'start' | 'end'
}) {
    return (
        <text
            data-testid={`print-quick-wins-quadrant-label-${quadrant}`}
            x={x}
            y={y}
            textAnchor={textAnchor}
            style={quadrantLabelStyle}
        >
            {QUADRANT_LABELS[quadrant].toUpperCase()}
        </text>
    )
}

// ── styles ────────────────────────────────────────────────────────

const svgStyle: CSSProperties = {
    width: '100%',
    height: 'auto',
    maxWidth: '100%',
}

const quadrantLabelStyle: CSSProperties = {
    fontSize: '9px',
    fontWeight: 700,
    fill: 'var(--text-tertiary)',
    letterSpacing: '0.06em',
}

const tickLabelStyle: CSSProperties = {
    fontSize: '10px',
    fill: 'var(--text-tertiary)',
}

const axisTitleStyle: CSSProperties = {
    fontSize: '11px',
    fontWeight: 600,
    fill: 'var(--text-secondary)',
}

const clampCaretStyle: CSSProperties = {
    fontSize: '9px',
    fill: 'var(--text-tertiary)',
}

const dotIndexStyle: CSSProperties = {
    fontSize: '9px',
    fill: 'var(--text-secondary)',
}

const clusterCountStyle: CSSProperties = {
    fontSize: '10px',
    fontWeight: 700,
    fill: 'white',
}
