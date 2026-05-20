'use client'

import { useEffect, useRef, useState, type CSSProperties, type FocusEvent } from 'react'

import QuickWinsOverflowBadge from '@/components/analysis/QuickWinsOverflowBadge'
import { useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import type { Opportunity } from '@/lib/types/api'
import { LEVER_COLORS } from '@/lib/utils/leverColors'
import type { Quadrant } from '@/lib/utils/quickWinsMatrixLayout'
import { QUADRANT_LABELS } from '@/lib/utils/quickWinsMatrixLayout'

/**
 * Single cell of the Quick Wins matrix. Renders:
 *
 *   - Up to ``MAX_VISIBLE_CHIPS`` opportunity title chips, stacked
 *     vertically. Each chip pairs a small ``value_lever``-coloured
 *     dot with the opportunity title (truncated with ellipsis).
 *   - A ``+N more`` overflow badge when
 *     ``opportunityIndices.length`` exceeds ``MAX_VISIBLE_CHIPS``.
 *     Clicking the badge opens a popover listing every opportunity
 *     in this cell.
 *   - A muted quadrant label in the four corner cells ("Quick Wins",
 *     "Strategic Bets", "Fill-Ins", "Deprioritise"). Center-axis
 *     cells get no label.
 *
 * The original P7 design used bare dots that required hover to surface
 * the opportunity title. In practice the AI clusters most opportunities
 * into the High × Medium-term cell, so the dot-only render produced a
 * single cluster of unlabelled dots — the reader couldn't tell what
 * the matrix was showing without per-dot hover. Replacing the dots
 * with title chips means every cell reads at a glance even when the
 * dataset clusters, while preserving the cross-section hover wiring.
 *
 * Each chip is a real ``<button>`` so it's reachable by keyboard tab
 * order and announceable by screen readers. Activation (click, Enter,
 * Space) publishes a hover-highlight via ``OpportunityHoverProvider``
 * → matching opportunity card pulses + scrolls into view. Focus / blur
 * mirror the same dispatch so keyboard navigation produces the same
 * effect as a mouse hover.
 */

/** Visible chips per cell before the ``+N more`` overflow badge kicks
 *  in. Lower than the original dot threshold (7) because title chips
 *  take ~3× the vertical real estate of bare dots — keeping more than
 *  four inline would blow out the cell height and crowd the page. */
const MAX_VISIBLE_CHIPS = 4

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
    const hasOverflow = opportunityIndices.length > MAX_VISIBLE_CHIPS
    const visibleIndices = hasOverflow ? opportunityIndices.slice(0, MAX_VISIBLE_CHIPS) : opportunityIndices
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
                <div style={chipStackStyle} ref={popoverContainerRef}>
                    {visibleIndices.map((opportunityIndex) => (
                        <QuickWinsChip
                            key={opportunityIndex}
                            opportunityIndex={opportunityIndex}
                            opportunity={opportunities[opportunityIndex]}
                        />
                    ))}
                    {hasOverflow ? (
                        <QuickWinsOverflowBadge
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
 * One opportunity chip — lever-coloured dot + the opportunity title
 * (truncated). Clicking, pressing Enter / Space, or focusing publishes
 * the linked-opportunity highlight via the hover provider so the
 * matching opportunity card below applies the ``.card-pulse`` class.
 *
 * **Click is a navigation gesture**: in addition to the highlight
 * dispatch, click imperatively scrolls the matching opportunity card
 * into view. Hover and focus do NOT scroll — the hover provider was
 * decoupled from scroll behaviour post-P1b after PE readers complained
 * that hovering a strategy-map cell pulled the page out from under
 * them. The matrix click stays click-to-navigate because it's the only
 * place on the page where the user can pick a specific opportunity
 * and expect to land on it.
 *
 * Test ID stays ``quick-wins-dot-{n}`` for backwards compatibility with
 * tests that pin the per-opportunity surface — what the surface looks
 * like changed (dot → chip), but it's still the same hover-source
 * primitive at the same coordinate.
 */
function QuickWinsChip({
    opportunityIndex,
    opportunity,
}: {
    opportunityIndex: number
    opportunity: Opportunity
}) {
    const { highlightOpportunities, clearHighlight } = useOpportunityHover()

    const onActivate = () => highlightOpportunities([opportunityIndex])

    const onClick = () => {
        highlightOpportunities([opportunityIndex])
        // Imperative scroll — click is intentional navigation. The
        // matching opportunity card carries ``opportunity-card-{n}``
        // testid from ``HoverableOpportunityCard``; query directly
        // rather than threading a ref through the hover provider
        // because we don't need any reactive state.
        const target = document.querySelector(`[data-testid="opportunity-card-${opportunityIndex}"]`)
        target?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }

    const onBlur = (event: FocusEvent<HTMLButtonElement>) => {
        // Same containment guard EBITDA / value chain / strategy map
        // use — protects against future inline buttons or children
        // (none today, but the pattern is symmetric).
        if (event.currentTarget.contains(event.relatedTarget as Node | null)) return
        clearHighlight()
    }

    const lever = opportunity.value_lever ?? 'Both'
    const color = LEVER_COLORS[lever] ?? 'var(--text-tertiary)'
    const hoverTitle = `${opportunity.title} (${lever})`

    return (
        <button
            type="button"
            data-testid={`quick-wins-dot-${opportunityIndex}`}
            aria-label={`Highlight opportunity: ${opportunity.title}`}
            title={hoverTitle}
            onClick={onClick}
            onMouseEnter={onActivate}
            onMouseLeave={clearHighlight}
            onFocus={onActivate}
            onBlur={onBlur}
            style={chipButtonStyle}
        >
            <span style={{ ...chipDotStyle, background: color }} aria-hidden="true" />
            <span style={chipLabelStyle}>{opportunity.title}</span>
        </button>
    )
}

// ── styles ─────────────────────────────────────────────────────────

const cellStyle: CSSProperties = {
    position: 'relative',
    // Top-padding accommodates the absolute-positioned corner quadrant
    // label without it overlapping the first chip. Bottom-padding does
    // the same for bottom-row labels.
    padding: '24px 8px 24px 8px',
    minHeight: '96px',
    border: '1px solid var(--border-subtle)',
    background: 'var(--bg-surface-2)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'stretch',
    justifyContent: 'flex-start',
    gap: '4px',
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
        pointerEvents: 'none',
    }
}

const chipStackStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    minWidth: 0,
}

const chipButtonStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    width: '100%',
    minWidth: 0,
    padding: '4px 8px',
    background: 'var(--bg-surface-3)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '6px',
    cursor: 'pointer',
    textAlign: 'left',
    font: 'inherit',
    color: 'var(--text-primary)',
}

const chipDotStyle: CSSProperties = {
    flex: '0 0 auto',
    display: 'inline-block',
    width: '8px',
    height: '8px',
    borderRadius: '50%',
}

const chipLabelStyle: CSSProperties = {
    flex: '1 1 auto',
    minWidth: 0,
    fontSize: '0.75rem',
    lineHeight: 1.3,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
}
