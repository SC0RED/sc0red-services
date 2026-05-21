'use client'

import { useCallback, useState, type CSSProperties } from 'react'

import { useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import type { Opportunity } from '@/lib/types/api'
import { LEVER_COLORS } from '@/lib/utils/leverColors'
import { QUADRANT_LABELS, type ClusterPin } from '@/lib/utils/quickWinsMatrixLayout'

/**
 * Cluster pin replacing a quadrant's individual dots when it exceeds
 * the ``CLUSTER_THRESHOLD``. Click toggles a popover listing every
 * opportunity in the quadrant — each entry is a button that pulses +
 * scrolls its matching opportunity card into view, mirroring the
 * single-dot click behaviour from ``ScatterDot``.
 *
 * The popover lives inside an SVG ``<foreignObject>`` so we can render
 * normal HTML (a scrollable ``<ul>``) inline with the SVG markers.
 */
export default function ClusterPinMarker({
    pin,
    opportunities,
}: {
    pin: ClusterPin
    opportunities: Opportunity[]
}) {
    const [isOpen, setIsOpen] = useState(false)
    const { highlightOpportunities } = useOpportunityHover()

    const onEntryClick = useCallback(
        (opportunityIndex: number) => {
            highlightOpportunities([opportunityIndex])
            const target = document.querySelector(`[data-testid="opportunity-card-${opportunityIndex}"]`)
            target?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
            setIsOpen(false)
        },
        [highlightOpportunities]
    )

    return (
        <g data-testid={`quick-wins-cluster-${pin.quadrant}`} transform={`translate(${pin.x}, ${pin.y})`}>
            <g
                role="button"
                tabIndex={0}
                aria-label={`${pin.opportunityIndices.length} opportunities in ${QUADRANT_LABELS[pin.quadrant]}`}
                onClick={() => setIsOpen((prev) => !prev)}
                onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        setIsOpen((prev) => !prev)
                    }
                    if (event.key === 'Escape' && isOpen) {
                        event.preventDefault()
                        setIsOpen(false)
                    }
                }}
                style={{ cursor: 'pointer' }}
            >
                <circle r={14} fill="var(--accent-blue)" stroke="var(--bg-surface)" strokeWidth={2} />
                <text textAnchor="middle" dy={4} style={clusterCountStyle}>
                    +{pin.opportunityIndices.length}
                </text>
            </g>
            {isOpen ? (
                <foreignObject
                    x={16}
                    y={-8}
                    width={260}
                    height={Math.min(280, 24 + pin.opportunityIndices.length * 28)}
                >
                    {/* foreignObject hosts HTML inside the SVG. Browsers
                        automatically apply the XHTML namespace to direct
                        children, so no explicit xmlns is required and
                        React's HTML types don't allow it. */}
                    <div
                        role="dialog"
                        aria-label={`Opportunities in ${QUADRANT_LABELS[pin.quadrant]}`}
                        data-testid={`quick-wins-cluster-popover-${pin.quadrant}`}
                        style={clusterPopoverStyle}
                    >
                        <ul style={clusterListStyle}>
                            {pin.opportunityIndices.map((opportunityIndex) => {
                                const opportunity = opportunities[opportunityIndex]
                                if (!opportunity) {
                                    throw new Error(
                                        `QuickWinsMatrix: cluster pin opportunity index ${opportunityIndex} ` +
                                            `is out of range (opportunities.length=${opportunities.length}). ` +
                                            'Layout helper should have filtered out unknowns.'
                                    )
                                }
                                const lever = opportunity.value_lever ?? 'Both'
                                const color = LEVER_COLORS[lever] ?? 'var(--text-tertiary)'
                                return (
                                    <li key={opportunityIndex}>
                                        <button
                                            type="button"
                                            data-testid={`quick-wins-cluster-item-${pin.quadrant}-${opportunityIndex}`}
                                            onClick={() => onEntryClick(opportunityIndex)}
                                            style={clusterItemStyle}
                                        >
                                            <span
                                                aria-hidden="true"
                                                style={{ ...clusterItemDot, background: color }}
                                            />
                                            <span style={clusterItemTitle}>{opportunity.title}</span>
                                        </button>
                                    </li>
                                )
                            })}
                        </ul>
                    </div>
                </foreignObject>
            ) : null}
        </g>
    )
}

// ── styles ────────────────────────────────────────────────────────

const clusterCountStyle: CSSProperties = {
    fontSize: '11px',
    fontWeight: 700,
    fill: 'white',
}

const clusterPopoverStyle: CSSProperties = {
    background: 'var(--bg-surface-3)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '8px',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.22)',
    padding: '6px',
    maxHeight: '260px',
    overflowY: 'auto',
}

const clusterListStyle: CSSProperties = {
    listStyle: 'none',
    margin: 0,
    padding: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
}

const clusterItemStyle: CSSProperties = {
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

const clusterItemDot: CSSProperties = {
    flex: '0 0 auto',
    display: 'inline-block',
    width: '8px',
    height: '8px',
    borderRadius: '50%',
}

const clusterItemTitle: CSSProperties = {
    flex: '1 1 auto',
    minWidth: 0,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
}
