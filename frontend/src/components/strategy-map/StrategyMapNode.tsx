'use client'

import { useState } from 'react'
import { Handle, type NodeProps, Position, type Node } from '@xyflow/react'

import type { ConfidenceMarker } from '@/lib/types/api'
import type { StrategyMapNodeData } from '@/lib/strategyMap/layout'

import ConfidenceChip from './ConfidenceChip'

/**
 * Custom React Flow node for the strategy-map canvas.
 *
 * Mirrors the structure of `EbitdaNodeComponent.tsx` (the EBITDA tree's
 * custom node) so the analysis page has one consistent node-detail
 * pattern: small chip in the canvas, hover or focus surfaces a tooltip
 * with full content. Tap on touch devices triggers React Flow's default
 * selection behaviour, which we treat the same as hover here.
 *
 * Default chip content:
 *   - Objective ID in monospace (cross-references in arrows + gaps stay
 *     readable when users scan the map).
 *   - Single-line title with CSS ellipsis.
 *   - 8 px circular confidence dot using the existing risk-tier palette.
 *
 * Hover / focus tooltip:
 *   - Full definition paragraph.
 *   - The literal HIGH / MEDIUM / LOW label via the existing
 *     `ConfidenceChip` component.
 *   - The `rationale_source` traceability note when the AI supplied one.
 */

const CHIP_WIDTH = 220
const CHIP_HEIGHT = 64

/** Palette per the change spec — reuses existing risk-tier tokens. */
const CONFIDENCE_DOT: Record<ConfidenceMarker, string> = {
    HIGH: 'var(--risk-low)',
    MEDIUM: 'var(--risk-moderate)',
    LOW: 'var(--risk-high)',
}

/** Slight visual differentiation per perspective via a left-border accent. */
const PERSPECTIVE_ACCENT: Record<StrategyMapNodeData['perspective'], string> = {
    financial: 'var(--accent-blue)',
    customer: 'var(--risk-low)',
    internal: 'var(--risk-moderate)',
    capacity: 'var(--text-secondary)',
}

export default function StrategyMapNode({ data, selected }: NodeProps<Node<StrategyMapNodeData>>) {
    const [hovered, setHovered] = useState(false)
    // Treat React Flow's `selected` (set on tap-to-focus) as equivalent to
    // hover so touch users see the same tooltip without a second tap.
    const showDetail = hovered || Boolean(selected)
    const accent = PERSPECTIVE_ACCENT[data.perspective]
    const renderedTitle = data.customerVoice ? `“${data.title}”` : data.title
    // Stable id for aria-controls so screen readers announce the
    // tooltip-as-detail of the node.
    const tooltipId = `strategy-map-node-detail-${data.objectiveId}`

    return (
        <div
            role="button"
            tabIndex={0}
            aria-label={`${data.objectiveId}: ${data.title}`}
            aria-describedby={showDetail ? tooltipId : undefined}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            onFocus={() => setHovered(true)}
            onBlur={() => setHovered(false)}
            onKeyDown={(event) => {
                // WCAG 2.1.1: a `role="button"` element MUST activate on
                // Enter and Space. Activation here means "open the tooltip
                // detail" — the same effect mouse hover and tap-to-focus
                // already produce. Without this handler, keyboard users
                // who tab to the chip get the tooltip via `onFocus` only,
                // not via Enter/Space, which violates the role's contract.
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    setHovered((current) => !current)
                }
            }}
            style={{
                position: 'relative',
                width: CHIP_WIDTH,
                height: CHIP_HEIGHT,
                padding: '8px 12px',
                background: 'var(--bg-surface-2)',
                border: '1px solid var(--border-subtle)',
                // Centre-lane chips (those that the layout helper couldn't
                // anchor to a real theme column) get a dashed accent
                // instead of solid, so the reader can spot "no theme home"
                // chips at a glance rather than having to map X-position
                // against the theme columns. The marker disappears under
                // the planned `β` follow-up where every objective has
                // explicit theme membership and centre-lane never fires.
                borderLeft: `3px ${data.inSharedLane ? 'dashed' : 'solid'} ${accent}`,
                borderRadius: '8px',
                boxShadow: showDetail ? '0 4px 16px rgba(0,0,0,0.25)' : '0 1px 3px rgba(0,0,0,0.15)',
                cursor: 'pointer',
                transition: 'box-shadow 0.15s ease',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                justifyContent: 'center',
            }}
        >
            {/* Inbound handle — top edge. Renders as a tiny dot for the edge router. */}
            <Handle
                type="target"
                position={Position.Top}
                style={{ background: accent, border: 'none', width: 6, height: 6 }}
            />
            <header
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    minWidth: 0,
                }}
            >
                <span
                    style={{
                        fontFamily: 'var(--font-mono, monospace)',
                        fontSize: '0.65rem',
                        fontWeight: 700,
                        color: 'var(--text-tertiary)',
                        flexShrink: 0,
                    }}
                >
                    {data.objectiveId}
                </span>
                <span
                    aria-hidden="true"
                    title={`Confidence: ${data.confidence}`}
                    style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: CONFIDENCE_DOT[data.confidence],
                        flexShrink: 0,
                    }}
                />
                {data.capacityBucket ? (
                    <span
                        style={{
                            fontSize: '0.6rem',
                            fontWeight: 700,
                            textTransform: 'uppercase',
                            color: 'var(--text-tertiary)',
                            letterSpacing: '0.06em',
                            flexShrink: 0,
                        }}
                    >
                        {data.capacityBucket}
                    </span>
                ) : null}
            </header>
            <div
                style={{
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    color: 'var(--text-primary)',
                    fontStyle: data.customerVoice ? 'italic' : 'normal',
                    lineHeight: 1.3,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                }}
            >
                {renderedTitle}
            </div>

            {/* Outbound handle — bottom edge. */}
            <Handle
                type="source"
                position={Position.Bottom}
                style={{ background: accent, border: 'none', width: 6, height: 6 }}
            />

            {showDetail ? (
                <div
                    id={tooltipId}
                    role="tooltip"
                    style={{
                        position: 'absolute',
                        top: '100%',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        marginTop: '8px',
                        width: 280,
                        padding: '12px 14px',
                        background: 'var(--bg-surface-3)',
                        border: '1px solid var(--border-strong)',
                        borderRadius: '8px',
                        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
                        zIndex: 50,
                        backdropFilter: 'blur(8px)',
                    }}
                >
                    <div
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: '8px',
                            marginBottom: '8px',
                        }}
                    >
                        <strong
                            style={{
                                fontSize: '0.85rem',
                                color: 'var(--text-primary)',
                                fontStyle: data.customerVoice ? 'italic' : 'normal',
                                lineHeight: 1.4,
                            }}
                        >
                            {renderedTitle}
                        </strong>
                        <ConfidenceChip confidence={data.confidence} />
                    </div>
                    <p
                        style={{
                            margin: 0,
                            fontSize: '0.78rem',
                            color: 'var(--text-secondary)',
                            lineHeight: 1.6,
                            whiteSpace: 'pre-line',
                        }}
                    >
                        {data.definition}
                    </p>
                    {data.rationaleSource ? (
                        <p
                            style={{
                                margin: '8px 0 0',
                                paddingTop: '8px',
                                borderTop: '1px solid var(--border-subtle)',
                                fontSize: '0.7rem',
                                fontStyle: 'italic',
                                color: 'var(--text-tertiary)',
                                lineHeight: 1.5,
                            }}
                        >
                            Source: {data.rationaleSource}
                        </p>
                    ) : null}
                </div>
            ) : null}
        </div>
    )
}
