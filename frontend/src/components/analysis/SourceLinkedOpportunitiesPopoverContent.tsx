'use client'

import type { CSSProperties } from 'react'

import { useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import type { Opportunity } from '@/lib/types/api'
import { LEVER_COLORS } from '@/lib/utils/leverColors'

/**
 * The visible popover body — header + list of opportunity entries +
 * overflow row. Extracted from ``SourceLinkedOpportunitiesPopover``
 * so the parent file (with its timer logic + lifecycle hooks) stays
 * under the 360-line frontend size limit. This file owns:
 *
 *   - The popover's outer styled container (``role="dialog"``, ARIA
 *     label, mouse handlers for transit grace).
 *   - The per-opportunity entry buttons (lever-coloured dot + truncated
 *     title) and their click → scroll + highlight wiring.
 *   - The "+N more" overflow row that scrolls to the OpportunitiesList
 *     section when clicked.
 *
 * The parent owns the open/close state, timers, and the popover-ref
 * + handlers that the lifecycle needs to coordinate. Splitting along
 * "presentation vs lifecycle" was the cleanest seam.
 */

/** Mirror of the parent's constant — exported so tests can reference
 *  the threshold without poking at internals. */
export const MAX_INLINE_TITLES = 5

interface PopoverContentProps {
    anchorId: string
    linkedIndices: number[]
    opportunities: Opportunity[]
    popoverDomId: string
    // ``Ref<HTMLDivElement>`` (not ``RefObject<HTMLDivElement | null>``)
    // because we forward the ref directly onto the inner ``<div>``.
    // Pre-React-19 the JSX type for ``ref`` on a host element is
    // ``LegacyRef`` which accepts ``RefObject<HTMLDivElement>`` but not
    // the nullable form.
    popoverRef: React.Ref<HTMLDivElement>
    onMouseEnter: () => void
    onMouseLeave: () => void
    onKeyDown: (event: React.KeyboardEvent<HTMLDivElement>) => void
    onClose: () => void
}

export default function SourceLinkedOpportunitiesPopoverContent({
    anchorId,
    linkedIndices,
    opportunities,
    popoverDomId,
    popoverRef,
    onMouseEnter,
    onMouseLeave,
    onKeyDown,
    onClose,
}: PopoverContentProps) {
    const { highlightOpportunities } = useOpportunityHover()

    const visibleIndices =
        linkedIndices.length > MAX_INLINE_TITLES ? linkedIndices.slice(0, MAX_INLINE_TITLES) : linkedIndices
    const overflowCount = linkedIndices.length - visibleIndices.length

    const onEntryActivate = (opportunityIndex: number) => {
        highlightOpportunities([opportunityIndex])
        // Imperative scroll — clicking an entry is intentional
        // navigation, same semantics as the QuickWinsMatrix chip
        // click. The matching opportunity card carries the
        // ``opportunity-card-{n}`` testid from
        // ``HoverableOpportunityCard``.
        const target = document.querySelector(`[data-testid="opportunity-card-${opportunityIndex}"]`)
        target?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
        onClose()
    }

    const onOverflowClick = () => {
        // Spec: clicking the "+N more" row falls back to scrolling the
        // OpportunitiesList section into view. A filtered-list mode
        // is out of scope for this PR.
        const target = document.querySelector('[data-testid="analysis-section-opportunities"]')
        target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        onClose()
    }

    return (
        <div
            ref={popoverRef}
            id={popoverDomId}
            role="dialog"
            aria-label="Linked opportunities"
            data-testid={`source-linked-popover-${anchorId}`}
            onMouseEnter={onMouseEnter}
            onMouseLeave={onMouseLeave}
            onKeyDown={onKeyDown}
            style={popoverStyle}
        >
            <div style={popoverHeaderStyle}>
                {linkedIndices.length === 1
                    ? '1 linked opportunity'
                    : `${linkedIndices.length} linked opportunities`}
            </div>
            <ul style={listStyle}>
                {visibleIndices.map((opportunityIndex) => {
                    const opportunity = opportunities[opportunityIndex]
                    if (!opportunity) {
                        // P1b's assembly-layer clip guarantees every
                        // index is in range by the time it reaches the
                        // UI. Reaching here means either the clip was
                        // bypassed (legacy persisted record) or the
                        // caller passed a malformed array. Fail loud
                        // rather than silently dropping the entry —
                        // a missing item in the popover is worse than
                        // a thrown error that surfaces the upstream
                        // bug.
                        throw new Error(
                            `SourceLinkedOpportunitiesPopover: opportunity index ${opportunityIndex} ` +
                                `is out of range (opportunities.length=${opportunities.length}). ` +
                                'P1b assembly clip should have removed it; this is a contract violation.'
                        )
                    }
                    const lever = opportunity.value_lever ?? 'Both'
                    const color = LEVER_COLORS[lever] ?? 'var(--text-tertiary)'
                    return (
                        <li key={opportunityIndex}>
                            <button
                                type="button"
                                data-testid={`source-linked-popover-item-${anchorId}-${opportunityIndex}`}
                                onClick={() => onEntryActivate(opportunityIndex)}
                                style={itemButtonStyle}
                            >
                                <span aria-hidden="true" style={{ ...itemDotStyle, background: color }} />
                                <span style={itemTitleStyle}>{opportunity.title}</span>
                            </button>
                        </li>
                    )
                })}
                {overflowCount > 0 ? (
                    <li>
                        <button
                            type="button"
                            data-testid={`source-linked-popover-overflow-${anchorId}`}
                            onClick={onOverflowClick}
                            style={overflowButtonStyle}
                        >
                            +{overflowCount} more — see opportunities list →
                        </button>
                    </li>
                ) : null}
            </ul>
        </div>
    )
}

// ── styles ─────────────────────────────────────────────────────────

const popoverStyle: CSSProperties = {
    position: 'absolute',
    top: 'calc(100% + 4px)',
    left: 0,
    minWidth: '260px',
    maxWidth: '360px',
    background: 'var(--bg-surface-3)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '8px',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.22)',
    padding: '8px',
    zIndex: 30,
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
}

const popoverHeaderStyle: CSSProperties = {
    fontSize: '0.75rem',
    fontWeight: 600,
    color: 'var(--text-tertiary)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    padding: '2px 8px',
}

const listStyle: CSSProperties = {
    listStyle: 'none',
    margin: 0,
    padding: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
}

const itemButtonStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
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

const itemDotStyle: CSSProperties = {
    flex: '0 0 auto',
    display: 'inline-block',
    width: '8px',
    height: '8px',
    borderRadius: '50%',
}

const itemTitleStyle: CSSProperties = {
    flex: '1 1 auto',
    minWidth: 0,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
}

const overflowButtonStyle: CSSProperties = {
    width: '100%',
    textAlign: 'left',
    background: 'transparent',
    border: 'none',
    borderTop: '1px solid var(--border-subtle)',
    padding: '8px',
    marginTop: '2px',
    fontSize: '0.75rem',
    color: 'var(--accent-blue)',
    cursor: 'pointer',
}
