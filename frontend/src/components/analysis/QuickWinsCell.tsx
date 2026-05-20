'use client'

import { useEffect, useRef, useState, type CSSProperties, type FocusEvent, type KeyboardEvent } from 'react'

import { useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import type { Opportunity } from '@/lib/types/api'
import { LEVER_COLORS } from '@/lib/utils/leverColors'
import type { Quadrant } from '@/lib/utils/quickWinsMatrixLayout'
import { QUADRANT_LABELS } from '@/lib/utils/quickWinsMatrixLayout'

/**
 * Single cell of the Quick Wins matrix. Renders:
 *
 *   - Up to ``MAX_VISIBLE_DOTS`` opportunity dots, stacked vertically
 *     with a 4 px offset between centres (per spec).
 *   - A ``+N more`` overflow badge when ``opportunityIndices.length``
 *     exceeds ``MAX_VISIBLE_DOTS``. Clicking the badge opens a
 *     popover listing every opportunity in this cell.
 *   - A muted quadrant label in the four corner cells ("Quick Wins",
 *     "Strategic Bets", "Fill-Ins", "Deprioritise"). Center-axis
 *     cells get no label.
 *
 * Each dot is a real ``<button role="button">`` so it's reachable by
 * keyboard tab order and announceable by screen readers. Activation
 * (click, Enter, Space) publishes a hover-highlight via
 * ``OpportunityHoverProvider`` → matching opportunity card pulses
 * + scrolls into view. Focus / blur mirror the same dispatch so
 * keyboard navigation produces the same effect as a mouse hover.
 */

/** Spec: "If a cell would contain more than eight dots, the first
 *  seven dots SHALL render and the eighth slot SHALL be a `+N more`
 *  badge." */
const MAX_VISIBLE_DOTS = 7

const DOT_SIZE = 10
const DOT_GAP = 4

interface QuickWinsCellProps {
    rowIndex: number
    columnIndex: number
    quadrant: Quadrant
    /** Original positions in ``opportunities`` (sorted by category +
     *  index by the layout helper). May be empty. */
    opportunityIndices: number[]
    /** Full opportunities array so the dot can render its
     *  ``value_lever`` colour and the popover can show titles. */
    opportunities: Opportunity[]
}

export default function QuickWinsCell({
    rowIndex,
    columnIndex,
    quadrant,
    opportunityIndices,
    opportunities,
}: QuickWinsCellProps) {
    const hasOverflow = opportunityIndices.length > MAX_VISIBLE_DOTS
    const visibleIndices = hasOverflow ? opportunityIndices.slice(0, MAX_VISIBLE_DOTS) : opportunityIndices
    const overflowCount = opportunityIndices.length - visibleIndices.length

    const [overflowOpen, setOverflowOpen] = useState(false)

    // Close popover on outside click. The keyboard ``Escape`` close is
    // wired on the popover itself.
    const popoverContainerRef = useRef<HTMLDivElement>(null)
    useEffect(() => {
        if (!overflowOpen) return
        const onDocClick = (event: MouseEvent) => {
            if (!popoverContainerRef.current) return
            if (!popoverContainerRef.current.contains(event.target as Node)) {
                setOverflowOpen(false)
            }
        }
        document.addEventListener('mousedown', onDocClick)
        return () => document.removeEventListener('mousedown', onDocClick)
    }, [overflowOpen])

    return (
        <div
            data-testid={`quick-wins-cell-${rowIndex}-${columnIndex}`}
            data-quadrant={quadrant ?? 'center'}
            style={cellStyle}
        >
            {quadrant ? (
                <span style={quadrantLabelStyle(rowIndex, columnIndex)}>{QUADRANT_LABELS[quadrant]}</span>
            ) : null}

            {opportunityIndices.length === 0 ? null : (
                <div style={dotStackStyle} ref={popoverContainerRef}>
                    {visibleIndices.map((opportunityIndex) => (
                        <QuickWinsDot
                            key={opportunityIndex}
                            opportunityIndex={opportunityIndex}
                            opportunity={opportunities[opportunityIndex]}
                        />
                    ))}
                    {hasOverflow ? (
                        <OverflowBadge
                            overflowCount={overflowCount}
                            allIndices={opportunityIndices}
                            opportunities={opportunities}
                            open={overflowOpen}
                            onToggle={() => setOverflowOpen((prev) => !prev)}
                            onClose={() => setOverflowOpen(false)}
                        />
                    ) : null}
                </div>
            )}
        </div>
    )
}

/**
 * One opportunity dot. Clicking, pressing Enter / Space, or focusing
 * publishes the linked-opportunity highlight. The dispatch is
 * symmetric across input modes so keyboard users and mouse users see
 * the same highlight + scroll behaviour.
 */
function QuickWinsDot({
    opportunityIndex,
    opportunity,
}: {
    opportunityIndex: number
    opportunity: Opportunity
}) {
    const { highlightOpportunities, clearHighlight } = useOpportunityHover()

    const onActivate = () => highlightOpportunities([opportunityIndex])

    const onBlur = (event: FocusEvent<HTMLButtonElement>) => {
        // Same containment guard EBITDA / value chain / strategy map
        // use — protects against future inline buttons or children
        // (none today, but the pattern is symmetric).
        if (event.currentTarget.contains(event.relatedTarget as Node | null)) return
        clearHighlight()
    }

    const lever = opportunity.value_lever ?? 'Both'
    const color = LEVER_COLORS[lever] ?? 'var(--text-tertiary)'
    const title = `${opportunity.title} (${lever})`

    return (
        <button
            type="button"
            data-testid={`quick-wins-dot-${opportunityIndex}`}
            aria-label={`Highlight opportunity: ${opportunity.title}`}
            title={title}
            onClick={onActivate}
            onMouseEnter={onActivate}
            onMouseLeave={clearHighlight}
            onFocus={onActivate}
            onBlur={onBlur}
            style={{ ...dotButtonStyle, background: color }}
        />
    )
}

interface OverflowBadgeProps {
    overflowCount: number
    allIndices: number[]
    opportunities: Opportunity[]
    open: boolean
    onToggle: () => void
    onClose: () => void
}

function OverflowBadge({
    overflowCount,
    allIndices,
    opportunities,
    open,
    onToggle,
    onClose,
}: OverflowBadgeProps) {
    const { highlightOpportunities } = useOpportunityHover()

    const onPopoverKey = (event: KeyboardEvent<HTMLDivElement>) => {
        if (event.key === 'Escape') {
            event.preventDefault()
            onClose()
        }
    }

    return (
        <div style={{ position: 'relative', display: 'inline-flex' }}>
            <button
                type="button"
                data-testid="quick-wins-overflow-badge"
                aria-expanded={open}
                aria-haspopup="dialog"
                onClick={onToggle}
                style={overflowBadgeStyle}
            >
                +{overflowCount} more
            </button>
            {open ? (
                <div
                    role="dialog"
                    aria-label="All opportunities in this cell"
                    data-testid="quick-wins-overflow-popover"
                    onKeyDown={onPopoverKey}
                    style={popoverStyle}
                >
                    <ul style={popoverListStyle}>
                        {allIndices.map((opportunityIndex) => {
                            const opp = opportunities[opportunityIndex]
                            return (
                                <li key={opportunityIndex}>
                                    <button
                                        type="button"
                                        data-testid={`quick-wins-popover-item-${opportunityIndex}`}
                                        onClick={() => {
                                            highlightOpportunities([opportunityIndex])
                                            onClose()
                                        }}
                                        style={popoverItemStyle}
                                    >
                                        {opp.title}
                                    </button>
                                </li>
                            )
                        })}
                    </ul>
                </div>
            ) : null}
        </div>
    )
}

// ── styles ─────────────────────────────────────────────────────────

const cellStyle: CSSProperties = {
    position: 'relative',
    padding: '12px 10px',
    minHeight: '90px',
    border: '1px solid var(--border-subtle)',
    background: 'var(--bg-surface-2)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '6px',
}

function quadrantLabelStyle(rowIndex: number, columnIndex: number): CSSProperties {
    // Anchor each corner quadrant label to its corner of the cell so the
    // four labels read as the corners of the matrix (top-left, top-right,
    // bottom-left, bottom-right).
    const top = rowIndex === 0 ? '6px' : 'auto'
    const bottom = rowIndex === 2 ? '6px' : 'auto'
    const left = columnIndex === 0 ? '8px' : 'auto'
    const right = columnIndex === 2 ? '8px' : 'auto'
    return {
        position: 'absolute',
        top,
        bottom,
        left,
        right,
        fontSize: '0.75rem',
        fontWeight: 600,
        color: 'var(--text-tertiary)',
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
    }
}

const dotStackStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: `${DOT_GAP}px`,
}

const dotButtonStyle: CSSProperties = {
    width: `${DOT_SIZE}px`,
    height: `${DOT_SIZE}px`,
    border: 'none',
    borderRadius: '50%',
    padding: 0,
    cursor: 'pointer',
}

const overflowBadgeStyle: CSSProperties = {
    background: 'var(--bg-surface-3)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '999px',
    padding: '2px 8px',
    fontSize: '0.75rem',
    color: 'var(--text-secondary)',
    cursor: 'pointer',
    marginTop: `${DOT_GAP}px`,
}

const popoverStyle: CSSProperties = {
    position: 'absolute',
    top: 'calc(100% + 4px)',
    left: '50%',
    transform: 'translateX(-50%)',
    minWidth: '220px',
    maxWidth: '320px',
    background: 'var(--bg-surface-3)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '8px',
    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.18)',
    padding: '6px',
    zIndex: 20,
}

const popoverListStyle: CSSProperties = {
    listStyle: 'none',
    padding: 0,
    margin: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
}

const popoverItemStyle: CSSProperties = {
    width: '100%',
    textAlign: 'left',
    background: 'transparent',
    border: 'none',
    padding: '6px 8px',
    borderRadius: '4px',
    fontSize: '0.75rem',
    color: 'var(--text-primary)',
    cursor: 'pointer',
}
