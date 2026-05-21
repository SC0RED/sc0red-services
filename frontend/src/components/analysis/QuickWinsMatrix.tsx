'use client'

import { type CSSProperties } from 'react'

import ClusterPinMarker from '@/components/analysis/quick-wins-matrix/ClusterPinMarker'
import ScatterDot from '@/components/analysis/quick-wins-matrix/ScatterDot'
import UncalibratedStrip from '@/components/analysis/quick-wins-matrix/UncalibratedStrip'
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

interface QuickWinsMatrixProps {
    opportunities: Opportunity[]
}

/**
 * ROI × Investment Matrix — true 2D scatter plot replacing the
 * pre-Phase-14 categorical 3×3. Plots every opportunity at its
 * (``investment_value_usd``, ``roi_estimate_pct``) coordinates,
 * routing rows with either axis ``null`` into a separate
 * "uncalibrated" strip below the chart.
 *
 * Design D8 of ``redesign-analysis-visuals``. Diagnostic Tool
 * Feedback #6 read literally — Zack asked for ROI × Investment, and
 * P7's categorical Path-C substitute was the wrong call.
 *
 * Quadrant split lines are drawn at the MEDIAN investment + median
 * ROI of the in-plot subset (per-scan, not fixed thresholds), so the
 * quadrant labels stay meaningful regardless of the analysis's
 * absolute scale.
 *
 * Sub-components live in ``quick-wins-matrix/`` to keep this file
 * under the 360-line frontend cap.
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
                top-left quadrant carries the highest-leverage near-term plays. Opportunities the AI
                couldn&rsquo;t size land in the uncalibrated strip below.
            </p>

            <ScatterPlot
                plotWidth={PLOT_WIDTH}
                plotHeight={PLOT_HEIGHT}
                layout={layout}
                opportunities={opportunities}
            />

            <UncalibratedStrip
                indices={layout.uncalibrated.map((u) => u.opportunityIndex)}
                opportunities={opportunities}
            />
        </div>
    )
}

// ── Scatter plot composition ──────────────────────────────────────

interface ScatterPlotProps {
    plotWidth: number
    plotHeight: number
    layout: ReturnType<typeof buildQuickWinsMatrixLayout>
    opportunities: Opportunity[]
}

function ScatterPlot({ plotWidth, plotHeight, layout, opportunities }: ScatterPlotProps) {
    // Axes margins — leave space outside the plot area for tick
    // labels + axis titles. The plot area itself sits at (margin.left,
    // margin.top) within the SVG viewBox; layout coordinates are
    // relative to the plot area, so we translate them in the render.
    const margin = { top: 16, right: 16, bottom: 56, left: 64 }
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
            aria-label="ROI versus Investment scatter plot. Each dot is one opportunity; the four quadrants are labelled Quick Wins (top-left), Strategic Bets (top-right), Fill-Ins (bottom-left), Deprioritise (bottom-right)."
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

                {/* Quadrant labels in corners */}
                <QuadrantCornerLabel quadrant="quick-wins" x={8} y={20} textAnchor="start" />
                <QuadrantCornerLabel quadrant="strategic-bets" x={plotWidth - 8} y={20} textAnchor="end" />
                <QuadrantCornerLabel quadrant="fill-ins" x={8} y={plotHeight - 10} textAnchor="start" />
                <QuadrantCornerLabel
                    quadrant="deprioritise"
                    x={plotWidth - 8}
                    y={plotHeight - 10}
                    textAnchor="end"
                />

                {/* Dots + cluster pins */}
                {layout.inPlot.map((dot) => (
                    <ScatterDot
                        key={`dot-${dot.opportunityIndex}`}
                        dot={dot}
                        opportunity={opportunities[dot.opportunityIndex]}
                    />
                ))}
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
                            <text y={18} textAnchor="middle" style={tickLabelStyle}>
                                {formatInvestmentTick(tick)}
                            </text>
                        </g>
                    )
                })}
                <text x={plotWidth / 2} y={42} textAnchor="middle" style={axisTitleStyle}>
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

// ── Quadrant label ────────────────────────────────────────────────

function QuadrantCornerLabel({
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
