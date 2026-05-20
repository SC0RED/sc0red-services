'use client'

import type { CSSProperties } from 'react'

import QuickWinsCell from '@/components/analysis/QuickWinsCell'
import type { Opportunity } from '@/lib/types/api'
import {
    IMPACT_ROW_ORDER,
    TIMELINE_COLUMN_LABELS,
    TIMELINE_COLUMN_ORDER,
    buildQuickWinsMatrixLayout,
} from '@/lib/utils/quickWinsMatrixLayout'

interface QuickWinsMatrixProps {
    opportunities: Opportunity[]
}

/**
 * Quick Wins 2×2 matrix (Phase 7 of ``redesign-analysis-visuals``).
 *
 * Renders every opportunity as a dot positioned by ``impact_rating``
 * (Y axis) × ``timeline`` (X axis) — a 3×3 grid that visually
 * collapses into four conceptual quadrants:
 *
 *   - Top-left  (High × Quick)  → "Quick Wins"
 *   - Top-right (High × Long)   → "Strategic Bets"
 *   - Bot-left  (Low × Quick)   → "Fill-Ins"
 *   - Bot-right (Low × Long)    → "Deprioritise"
 *
 * Center-axis cells (Medium impact row + Medium-term column) are
 * shared territory — no quadrant label. Per the spec, the matrix
 * uses categorical buckets (path C) instead of numeric ROI / investment
 * plotting (path B) because the AI fields are still free-text strings;
 * a future schema change adding ``investment_value: int`` + ``roi_pct:
 * float`` is on the back-burner for v1.
 *
 * Click / focus / hover any dot → ``OpportunityHoverProvider`` (P5)
 * publishes the linked-opportunity index → matching opportunity card
 * below pulses + scrolls into view.
 */
export default function QuickWinsMatrix({ opportunities }: QuickWinsMatrixProps) {
    const layout = buildQuickWinsMatrixLayout(opportunities)
    return (
        <div data-testid="quick-wins-matrix" style={containerStyle}>
            {/*
             * No ``AnalysisLegend`` here — the lever-color vocabulary is
             * already taught three times above (EBITDA, value chain,
             * strategy map). Repeating it on the page's last analysis
             * surface would read as redundant. Each dot's ``title``
             * attribute exposes the lever name verbatim on hover for
             * any reader who landed on the matrix without scrolling
             * past the upper sections.
             */}
            <p style={leadStyle}>
                Each opportunity is plotted by impact (vertical) and timeline (horizontal). Dots in the
                top-left quadrant are the highest-leverage near-term plays; bottom-right are low-impact,
                slow-payoff — deprioritise unless context shifts.
            </p>

            <div style={gridShellStyle}>
                <div style={emptyCornerStyle} />
                <div style={columnHeaderRowStyle(TIMELINE_COLUMN_ORDER.length)}>
                    {TIMELINE_COLUMN_ORDER.map((column, columnIndex) => (
                        <div
                            key={column}
                            data-testid={`quick-wins-column-header-${columnIndex}`}
                            style={columnHeaderStyle}
                        >
                            {TIMELINE_COLUMN_LABELS[column]}
                        </div>
                    ))}
                </div>

                <div style={rowLabelColumnStyle}>
                    {IMPACT_ROW_ORDER.map((impact, rowIndex) => (
                        <div
                            key={impact}
                            data-testid={`quick-wins-row-header-${rowIndex}`}
                            style={rowHeaderStyle}
                        >
                            {impact} impact
                        </div>
                    ))}
                </div>

                <div style={cellGridStyle(TIMELINE_COLUMN_ORDER.length)}>
                    {layout.cells.flatMap((row, rowIndex) =>
                        row.map((cell, columnIndex) => (
                            <QuickWinsCell
                                key={`${rowIndex}-${columnIndex}`}
                                rowIndex={rowIndex}
                                columnIndex={columnIndex}
                                quadrant={cell.quadrant}
                                opportunityIndices={cell.opportunityIndices}
                                opportunities={opportunities}
                            />
                        ))
                    )}
                </div>
            </div>
        </div>
    )
}

// ── styles ─────────────────────────────────────────────────────────

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

/** Outer grid: 1 fixed row-label column + N cell columns; 1 fixed
 *  column-header row + 1 cells row. Layout via display:grid with
 *  named regions would be tidier, but the simple two-track shape
 *  keeps the inline-style budget small and readable.
 */
const gridShellStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '110px 1fr',
    gridTemplateRows: 'auto 1fr',
    gap: '8px',
    alignItems: 'stretch',
}

const emptyCornerStyle: CSSProperties = {
    /* deliberate empty top-left corner */
}

function columnHeaderRowStyle(columnCount: number): CSSProperties {
    return {
        display: 'grid',
        gridTemplateColumns: `repeat(${columnCount}, 1fr)`,
        gap: '8px',
    }
}

const columnHeaderStyle: CSSProperties = {
    fontSize: '0.75rem',
    color: 'var(--text-tertiary)',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    textAlign: 'center',
}

const rowLabelColumnStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
}

const rowHeaderStyle: CSSProperties = {
    flex: '1 1 0',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'flex-end',
    fontSize: '0.75rem',
    color: 'var(--text-tertiary)',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    paddingRight: '8px',
}

function cellGridStyle(columnCount: number): CSSProperties {
    return {
        display: 'grid',
        gridTemplateColumns: `repeat(${columnCount}, 1fr)`,
        gridTemplateRows: 'repeat(3, 1fr)',
        gap: '8px',
    }
}
