'use client'

import { Handle, type NodeProps, NodeToolbar, Position, type Node } from '@xyflow/react'

import ConfidenceIndicator from '@/components/analysis/ConfidenceIndicator'
import { useHoverIntent } from '@/lib/hooks/useHoverIntent'
import { CHIP_HEIGHT, CHIP_WIDTH, type StrategyMapNodeData } from '@/lib/strategyMap/layout'

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
 *   - Compact `ConfidenceIndicator` (3-dot scale, neutral palette) so
 *     the chip header signals confidence without recruiting the
 *     risk-tier palette.
 *
 * Hover / focus tooltip:
 *   - Full definition paragraph.
 *   - Default-size `ConfidenceIndicator` with tooltip-on-hover for the
 *     long-form rationale.
 *   - The `rationale_source` traceability note when the AI supplied one.
 *
 * The tooltip is rendered through React Flow's `NodeToolbar` primitive,
 * which portals the content out of the canvas viewport into a top-level
 * container. That solves two production bugs reported in the
 * `fix/strategy-map-canvas-layout-bugs` change:
 *   - Sibling chips below the hovered chip would render ON TOP of the
 *     in-canvas tooltip (no z-index lift inside React Flow's per-node
 *     stacking context).
 *   - Long definitions on chips in the bottom band overflowed the
 *     canvas's `overflow: hidden` and got clipped.
 * The `NodeToolbar` portal escapes both issues at once.
 */

/** Slight visual differentiation per perspective via a left-border accent. */
const PERSPECTIVE_ACCENT: Record<StrategyMapNodeData['perspective'], string> = {
    financial: 'var(--accent-blue)',
    customer: 'var(--risk-low)',
    internal: 'var(--risk-moderate)',
    capacity: 'var(--text-secondary)',
}

export default function StrategyMapNode({ id, data, selected }: NodeProps<Node<StrategyMapNodeData>>) {
    // Hover state with safe-transit grace period — the tooltip lives in
    // NodeToolbar's portal so the cursor briefly leaves both chip and
    // tooltip during transit; without the grace period the tooltip
    // would close before the cursor could reach it. See useHoverIntent
    // for the full rationale + state machine.
    const { hovered, openNow, scheduleClose, setHovered } = useHoverIntent()
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
            onMouseEnter={openNow}
            onMouseLeave={scheduleClose}
            onFocus={openNow}
            onBlur={scheduleClose}
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
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        color: 'var(--text-tertiary)',
                        flexShrink: 0,
                    }}
                >
                    {data.objectiveId}
                </span>
                <ConfidenceIndicator confidence={data.confidence} size="small" />
                {data.capacityBucket ? (
                    <span
                        style={{
                            fontSize: '0.75rem',
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
                    fontSize: '0.75rem',
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

            {/*
             * NodeToolbar portals its content outside the React Flow viewport
             * via a top-level container, so the tooltip
             *   (a) is never clipped by the canvas's `overflow: hidden`
             *       (long definitions on bottom-band chips don't get cut),
             *   (b) is never covered by sibling chips' DOM order
             *       (each toolbar lifts onto its own stacking context).
             *
             * Position is `Bottom` for chips in the top three bands (financial,
             * customer, internal). For Capacity (the bottom band), it flips to
             * `Top` — the toolbar portal positions content with viewport-fixed
             * coords, so a `Bottom` tooltip on a capacity chip would render
             * BELOW the canvas's bottom edge and overlay the gaps panel + CTA
             * sitting directly underneath. Flipping puts capacity tooltips
             * inside the canvas's vertical range.
             *
             * `offset={8}` matches the previous in-chip `marginTop`.
             */}
            <NodeToolbar
                nodeId={id}
                isVisible={showDetail}
                position={data.perspective === 'capacity' ? Position.Top : Position.Bottom}
                offset={8}
            >
                <div
                    id={tooltipId}
                    role="tooltip"
                    // `nowheel` is React Flow's official escape hatch for
                    // wheel events: any element with this class (and any
                    // descendant) is excluded from the zoom-on-scroll
                    // handler. See the `noWheelClassName = 'nowheel'`
                    // default on `<ReactFlow>`. This is what makes
                    // wheel-over-tooltip scroll the inner overflow region
                    // instead of zooming the canvas. `stopPropagation` on
                    // its own wasn't enough because React Flow checks for
                    // the class on the wheel event's target before the
                    // zoom path runs, short-circuiting zoom regardless of
                    // bubble-phase propagation.
                    className="nowheel"
                    // Hover handlers on the tooltip body itself: when the
                    // cursor enters here, cancel any pending close so the
                    // user can scroll long definitions without the tooltip
                    // dismissing under them. When the cursor leaves the
                    // tooltip, schedule a close (the chip's mouseEnter
                    // would cancel it again if the user transits BACK).
                    onMouseEnter={openNow}
                    onMouseLeave={scheduleClose}
                    style={{
                        width: 280,
                        // Cap the tooltip height so very long definitions
                        // don't extend past the canvas (or, when flipped to
                        // Position.Top, off the top of the viewport). The
                        // header row stays put outside the scroll region;
                        // only the definition + rationale-source body
                        // scrolls. 320 px ≈ 8-9 lines of body text plus the
                        // header — enough that the typical 50-300 char
                        // definition fits without scrolling, while
                        // outliers (e.g. multi-paragraph definitions in
                        // very dense analyses) get a bounded UI rather
                        // than overlaying the gaps panel below.
                        maxHeight: 320,
                        display: 'flex',
                        flexDirection: 'column',
                        padding: '12px 14px',
                        background: 'var(--bg-surface-3)',
                        border: '1px solid var(--border-strong)',
                        borderRadius: '8px',
                        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
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
                            flexShrink: 0,
                        }}
                    >
                        <strong
                            style={{
                                fontSize: '0.875rem',
                                color: 'var(--text-primary)',
                                fontStyle: data.customerVoice ? 'italic' : 'normal',
                                lineHeight: 1.4,
                            }}
                        >
                            {renderedTitle}
                        </strong>
                        <ConfidenceIndicator confidence={data.confidence} />
                    </div>
                    <div
                        // Scrollable body. The header above stays pinned so
                        // the user always sees the chip's title + confidence,
                        // even when scrolling through a long definition.
                        style={{
                            overflowY: 'auto',
                            flex: 1,
                            minHeight: 0,
                        }}
                    >
                        <p
                            style={{
                                margin: 0,
                                fontSize: '0.75rem',
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
                                    fontSize: '0.75rem',
                                    fontStyle: 'italic',
                                    color: 'var(--text-tertiary)',
                                    lineHeight: 1.5,
                                }}
                            >
                                Source: {data.rationaleSource}
                            </p>
                        ) : null}
                    </div>
                </div>
            </NodeToolbar>
        </div>
    )
}
