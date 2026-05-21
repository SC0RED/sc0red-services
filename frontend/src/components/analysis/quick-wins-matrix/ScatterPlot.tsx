'use client'

import { type CSSProperties } from 'react'

import ClusterPinMarker from '@/components/analysis/quick-wins-matrix/ClusterPinMarker'
import ScatterDot from '@/components/analysis/quick-wins-matrix/ScatterDot'
import type { Opportunity } from '@/lib/types/api'
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
    type Quadrant,
} from '@/lib/utils/quickWinsMatrixLayout'

interface ScatterPlotProps {
    plotWidth: number
    plotHeight: number
    layout: ReturnType<typeof buildQuickWinsMatrixLayout>
    opportunities: Opportunity[]
}

/**
 * SVG scatter plot for the ROI × Investment matrix. Owns the chart
 * surface only — the wrapping ``QuickWinsMatrix`` is responsible for
 * the lead paragraph, the median-split caveat, the lever-colour
 * ``AnalysisLegend``, the sidebar ``OpportunityLegendColumn``, and the
 * uncalibrated footer strip.
 *
 * Quadrant labels live in the outer chart margin (above the plot for
 * Quick Wins / Strategic Bets, below for Fill-Ins / Deprioritise) so
 * they never overlap a dot in their own corner — the original design
 * placed them inside the plot and they collided with dense Quick Wins
 * clusters, which is exactly where readers focus first.
 */
export default function ScatterPlot({ plotWidth, plotHeight, layout, opportunities }: ScatterPlotProps) {
    // Axes margins — leave space outside the plot area for tick
    // labels + axis titles + quadrant labels. ``top`` and ``bottom``
    // are each tall enough to fit a row of quadrant labels above /
    // below the plot edge without crowding the X axis below.
    const margin = { top: 32, right: 16, bottom: 70, left: 64 }
    const svgWidth = plotWidth + margin.left + margin.right
    const svgHeight = plotHeight + margin.top + margin.bottom

    // Tick positions sourced from the shared axis constants so the
    // screen + print + layout helper all move together if the visual
    // cap ever changes.
    const xTicks = [INVESTMENT_MIN_USD, 100_000, 1_000_000, INVESTMENT_MAX_USD]
    const yTicks = [ROI_MIN_PCT, 100, 200, ROI_MAX_PCT]

    return (
        <svg
            data-testid="quick-wins-matrix-svg"
            role="img"
            aria-label="ROI versus Investment scatter plot. Each numbered dot is one opportunity; the four quadrants are labelled Quick Wins (top-left), Strategic Bets (top-right), Fill-Ins (bottom-left), Deprioritise (bottom-right). Use the legend column to resolve each numbered badge to an opportunity."
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            preserveAspectRatio="xMidYMid meet"
            style={svgStyle}
        >
            {/* Quadrant labels live in the OUTER margin — above the plot
                for the top-row labels, below the plot (just over the X
                axis ticks) for the bottom-row labels. Out-of-plot
                placement means a dot landing in a corner can never
                collide with its quadrant label, which was the
                original failure mode. */}
            <QuadrantOuterLabel
                quadrant="quick-wins"
                x={margin.left + 6}
                y={margin.top - 8}
                textAnchor="start"
            />
            <QuadrantOuterLabel
                quadrant="strategic-bets"
                x={margin.left + plotWidth - 6}
                y={margin.top - 8}
                textAnchor="end"
            />
            <QuadrantOuterLabel
                quadrant="fill-ins"
                x={margin.left + 6}
                y={margin.top + plotHeight + 16}
                textAnchor="start"
            />
            <QuadrantOuterLabel
                quadrant="deprioritise"
                x={margin.left + plotWidth - 6}
                y={margin.top + plotHeight + 16}
                textAnchor="end"
            />

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

                {/* Dots + cluster pins. Bounds-check the index from the
                    layout helper before we hand it to ``ScatterDot`` — the
                    sub-component declares ``opportunity: Opportunity`` (not
                    nullable), so a stale array slipping past the layout
                    helper would otherwise produce a silent TypeError deep
                    inside the renderer. Fail-fast matches the symmetric
                    guard in ``OpportunityLegendColumn.LegendEntry``. */}
                {layout.inPlot.map((dot) => {
                    const opportunity = opportunities[dot.opportunityIndex]
                    if (!opportunity) {
                        throw new Error(
                            `QuickWinsMatrix ScatterPlot: opportunity index ${dot.opportunityIndex} ` +
                                `out of range (opportunities.length=${opportunities.length}) — ` +
                                'caller likely passed a stale opportunities array to the layout helper.'
                        )
                    }
                    return (
                        <ScatterDot key={`dot-${dot.opportunityIndex}`} dot={dot} opportunity={opportunity} />
                    )
                })}
                {layout.clusterPins.map((pin) => (
                    <ClusterPinMarker
                        key={`cluster-${pin.quadrant}`}
                        pin={pin}
                        opportunities={opportunities}
                    />
                ))}
            </g>

            {/* X axis tick labels + title */}
            <g transform={`translate(${margin.left}, ${margin.top + plotHeight})`}>
                {xTicks.map((tick) => {
                    const x = projectInvestmentTickX(tick, plotWidth)
                    return (
                        <g key={`xtick-${tick}`} transform={`translate(${x}, 0)`}>
                            <line y1={0} y2={4} stroke="var(--text-tertiary)" />
                            <text y={32} textAnchor="middle" style={tickLabelStyle}>
                                {formatInvestmentTick(tick)}
                            </text>
                        </g>
                    )
                })}
                <text x={plotWidth / 2} y={56} textAnchor="middle" style={axisTitleStyle}>
                    Investment (USD, log scale)
                </text>
            </g>

            {/* Y axis tick labels + title */}
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
                    transform={`translate(${-48}, ${plotHeight / 2}) rotate(-90)`}
                    textAnchor="middle"
                    style={axisTitleStyle}
                >
                    ROI (%)
                </text>
            </g>
        </svg>
    )
}

function QuadrantOuterLabel({
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
            data-testid={`quick-wins-quadrant-label-${quadrant}`}
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
    fontSize: '11px',
    fontWeight: 700,
    fill: 'var(--text-tertiary)',
    letterSpacing: '0.08em',
}

const tickLabelStyle: CSSProperties = {
    fontSize: '11px',
    fill: 'var(--text-tertiary)',
}

const axisTitleStyle: CSSProperties = {
    fontSize: '12px',
    fontWeight: 600,
    fill: 'var(--text-secondary)',
}
