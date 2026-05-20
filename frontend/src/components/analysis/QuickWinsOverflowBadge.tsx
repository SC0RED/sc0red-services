'use client'

import type { CSSProperties, KeyboardEvent } from 'react'

import { useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import type { Opportunity } from '@/lib/types/api'

/**
 * Overflow badge + popover used by the Quick Wins matrix cells when a
 * cell would otherwise blow its chip budget (``MAX_VISIBLE_CHIPS`` in
 * ``QuickWinsCell``). Extracted from ``QuickWinsCell.tsx`` so that
 * file stays under the 360-line frontend size limit.
 *
 * Clicking the badge toggles a click-popover that lists every
 * opportunity in the cell. Each popover item is a button that, when
 * activated, publishes a hover-highlight (same provider the chips
 * use) and closes the popover.
 *
 * Accessibility:
 *   - Badge is a real ``<button>`` with ``aria-expanded`` + ``aria-haspopup``.
 *   - Popover is ``role="dialog"`` with an explicit ``aria-label`` so
 *     screen readers announce it with a name.
 *   - Escape closes via ``onKeyDown`` on the popover container.
 *
 * The outside-click close + the popover open / close lifecycle live
 * in ``QuickWinsCell``; this component is intentionally controlled.
 */
export interface QuickWinsOverflowBadgeProps {
    overflowCount: number
    /** All opportunity indices in the cell (visible + overflowed). The
     *  popover lists every entry; the visible/hidden split is only a
     *  rendering concern, not a data concern. */
    allIndices: number[]
    /** Full opportunities array — popover items resolve titles by
     *  index. */
    opportunities: Opportunity[]
    open: boolean
    onToggle: () => void
    onClose: () => void
}

export default function QuickWinsOverflowBadge({
    overflowCount,
    allIndices,
    opportunities,
    open,
    onToggle,
    onClose,
}: QuickWinsOverflowBadgeProps) {
    const { highlightOpportunities } = useOpportunityHover()

    const onPopoverKey = (event: KeyboardEvent<HTMLDivElement>) => {
        if (event.key === 'Escape') {
            event.preventDefault()
            onClose()
        }
    }

    return (
        <div style={containerStyle}>
            <button
                type="button"
                data-testid="quick-wins-overflow-badge"
                aria-expanded={open}
                aria-haspopup="dialog"
                onClick={onToggle}
                style={badgeStyle}
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

const containerStyle: CSSProperties = {
    position: 'relative',
    display: 'inline-flex',
}

const badgeStyle: CSSProperties = {
    background: 'var(--bg-surface-3)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '999px',
    padding: '2px 8px',
    fontSize: '0.75rem',
    color: 'var(--text-secondary)',
    cursor: 'pointer',
    marginTop: '2px',
    alignSelf: 'flex-start',
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
