import type { CSSProperties } from 'react'

import { findByOriginalIndex, type OpportunityWithIndex } from '@/lib/pdf/sortOpportunities'
import type { Opportunity } from '@/lib/types/api'
import { LEVER_COLORS } from '@/lib/utils/leverColors'
import {
    IMPACT_ROW_ORDER,
    QUADRANT_LABELS,
    TIMELINE_COLUMN_LABELS,
    TIMELINE_COLUMN_ORDER,
    buildQuickWinsMatrixLayout,
} from '@/lib/utils/quickWinsMatrixLayout'

interface PrintQuickWinsMatrixProps {
    /** Same sorted-with-original-index list used elsewhere in the PDF.
     *  Required so each dot can render its printed-index reference
     *  inline next to the opportunity title in the popover-equivalent
     *  list under each cell. */
    sortedOpportunities: OpportunityWithIndex[]
}

/**
 * Print-only Quick Wins matrix (Phase 7 of ``redesign-analysis-visuals``).
 *
 * Static parallel to the screen ``QuickWinsMatrix``: same 3×3 grid,
 * same quadrant labels, same dot positions, but with no event
 * handlers and no popover state. The dots survive as visual landmarks
 * in the PDF; the per-cell opportunity list under each cell makes the
 * dot-to-opportunity linkage explicit on paper (where hover doesn't
 * exist).
 *
 * Sits inside ``PrintReport.tsx`` between the opportunity list and
 * the back cover, gated on ``opportunities.length >= 1`` — matches
 * the screen rule.
 */
export default function PrintQuickWinsMatrix({ sortedOpportunities }: PrintQuickWinsMatrixProps) {
    // The matrix layout helper expects ``Opportunity[]`` in original-
    // index order — that's what every dot's ``opportunityIndices``
    // value points into. ``sortedOpportunities`` is a print-display
    // sort (by impact / lever) layered ON TOP of the original list, so
    // we rebuild an original-index-keyed array first.
    const opportunities = sortedOpportunities
        .slice()
        .sort((a, b) => a.originalIndex - b.originalIndex)
        .map((entry) => entry.opportunity) as Opportunity[]

    const layout = buildQuickWinsMatrixLayout(opportunities)

    return (
        <section className="print-section print-section--break-before print-quick-wins-matrix">
            <h2>Quick Wins Matrix</h2>

            <p style={leadStyle}>
                Each opportunity is plotted by impact (vertical) and timeline (horizontal). The top-left
                quadrant carries the highest-leverage near-term plays.
            </p>

            <div style={gridShellStyle}>
                <div />
                <div style={columnHeaderRowStyle(TIMELINE_COLUMN_ORDER.length)}>
                    {TIMELINE_COLUMN_ORDER.map((column) => (
                        <div key={column} style={columnHeaderStyle}>
                            {TIMELINE_COLUMN_LABELS[column]}
                        </div>
                    ))}
                </div>

                <div style={rowLabelColumnStyle}>
                    {IMPACT_ROW_ORDER.map((impact) => (
                        <div key={impact} style={rowHeaderStyle}>
                            {impact} impact
                        </div>
                    ))}
                </div>

                <div style={cellGridStyle(TIMELINE_COLUMN_ORDER.length)}>
                    {layout.cells.flatMap((row, rowIndex) =>
                        row.map((cell, columnIndex) => (
                            <PrintCell
                                key={`${rowIndex}-${columnIndex}`}
                                rowIndex={rowIndex}
                                columnIndex={columnIndex}
                                opportunityIndices={cell.opportunityIndices}
                                quadrantLabel={cell.quadrant ? QUADRANT_LABELS[cell.quadrant] : null}
                                opportunities={opportunities}
                                sortedOpportunities={sortedOpportunities}
                            />
                        ))
                    )}
                </div>
            </div>
        </section>
    )
}

function PrintCell({
    rowIndex,
    columnIndex,
    opportunityIndices,
    quadrantLabel,
    opportunities,
    sortedOpportunities,
}: {
    rowIndex: number
    columnIndex: number
    opportunityIndices: number[]
    quadrantLabel: string | null
    opportunities: Opportunity[]
    sortedOpportunities: OpportunityWithIndex[]
}) {
    return (
        <div style={cellStyle}>
            {quadrantLabel ? (
                <div style={quadrantLabelStyle(rowIndex, columnIndex)}>{quadrantLabel}</div>
            ) : null}
            <div style={dotStackStyle}>
                {opportunityIndices.map((originalIndex) => {
                    const opp = opportunities[originalIndex]
                    const lever = opp.value_lever ?? 'Both'
                    const color = LEVER_COLORS[lever] ?? 'var(--text-tertiary)'
                    return (
                        <span
                            key={originalIndex}
                            style={{ ...dotStyle, background: color }}
                            aria-hidden="true"
                        />
                    )
                })}
            </div>
            {opportunityIndices.length > 0 ? (
                <ul style={cellListStyle}>
                    {opportunityIndices.map((originalIndex) => {
                        // Resolve through the shared helper rather than an
                        // inline ``.find`` — matches PrintEbitdaOutline,
                        // PrintStrategyMapObjectives, PrintValueChainList.
                        // If the helper ever gains a stricter "throw on
                        // missing" mode the print components all upgrade
                        // together.
                        const entry = findByOriginalIndex(sortedOpportunities, originalIndex)
                        if (!entry) return null
                        return (
                            <li key={originalIndex} style={cellListItemStyle}>
                                #{entry.printedIndex} {entry.opportunity.title}
                            </li>
                        )
                    })}
                </ul>
            ) : null}
        </div>
    )
}

// ── styles ─────────────────────────────────────────────────────────

const leadStyle: CSSProperties = {
    margin: '0 0 12px',
    fontSize: '0.85rem',
    color: 'var(--text-secondary)',
    lineHeight: 1.5,
}

const gridShellStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '110px 1fr',
    gridTemplateRows: 'auto 1fr',
    gap: '6px',
}

function columnHeaderRowStyle(columnCount: number): CSSProperties {
    return {
        display: 'grid',
        gridTemplateColumns: `repeat(${columnCount}, 1fr)`,
        gap: '6px',
    }
}

const columnHeaderStyle: CSSProperties = {
    fontSize: '0.7rem',
    color: 'var(--text-tertiary)',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    textAlign: 'center',
}

const rowLabelColumnStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
}

const rowHeaderStyle: CSSProperties = {
    flex: '1 1 0',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'flex-end',
    paddingRight: '6px',
    fontSize: '0.7rem',
    color: 'var(--text-tertiary)',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
}

function cellGridStyle(columnCount: number): CSSProperties {
    return {
        display: 'grid',
        gridTemplateColumns: `repeat(${columnCount}, 1fr)`,
        gridTemplateRows: 'repeat(3, 1fr)',
        gap: '6px',
    }
}

const cellStyle: CSSProperties = {
    position: 'relative',
    padding: '10px 8px',
    minHeight: '60px',
    border: '1px solid var(--border-subtle)',
    background: 'var(--bg-surface-2)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'flex-start',
    gap: '6px',
}

function quadrantLabelStyle(rowIndex: number, columnIndex: number): CSSProperties {
    const top = rowIndex === 0 ? '4px' : 'auto'
    const bottom = rowIndex === 2 ? '4px' : 'auto'
    const left = columnIndex === 0 ? '6px' : 'auto'
    const right = columnIndex === 2 ? '6px' : 'auto'
    return {
        position: 'absolute',
        top,
        bottom,
        left,
        right,
        fontSize: '0.65rem',
        fontWeight: 700,
        color: 'var(--text-tertiary)',
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
    }
}

const dotStackStyle: CSSProperties = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '4px',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: '12px',
}

const dotStyle: CSSProperties = {
    display: 'inline-block',
    width: '8px',
    height: '8px',
    borderRadius: '50%',
}

const cellListStyle: CSSProperties = {
    listStyle: 'none',
    margin: 0,
    padding: 0,
    fontSize: '0.65rem',
    color: 'var(--text-secondary)',
    lineHeight: 1.4,
}

const cellListItemStyle: CSSProperties = {
    margin: 0,
}
