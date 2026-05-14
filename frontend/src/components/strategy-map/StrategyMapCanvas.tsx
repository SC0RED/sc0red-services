'use client'

import { useMemo, useRef, useState } from 'react'
import {
    Background,
    Controls,
    type Edge,
    MarkerType,
    type Node,
    ReactFlow,
    ReactFlowProvider,
    ViewportPortal,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import {
    COLUMN_WIDTH,
    type StrategyMapBand,
    type StrategyMapEdgeData,
    type StrategyMapNodeData,
    buildStrategyMapGraph,
    totalCanvasHeight,
} from '@/lib/strategyMap/layout'
import type { StrategyMap } from '@/lib/types/api'

import StrategyMapNode from './StrategyMapNode'

const NODE_TYPES = { strategyMap: StrategyMapNode }

/**
 * Display labels for each band, keyed by the layout's perspective name.
 * The canvas reads ``StrategyMapGraph.bands`` (one entry per perspective
 * in top-to-bottom narrative order) and looks up the label here. Keeps
 * label content separate from the geometry computation so the layout
 * helper has no opinion on copy.
 */
const PERSPECTIVE_LABELS: Record<StrategyMapBand['perspective'], { label: string; tagline: string }> = {
    financial: { label: 'Financial', tagline: 'Returns we generate' },
    customer: { label: 'Customer', tagline: 'What customers experience' },
    internal: { label: 'Internal Processes', tagline: 'What we do operationally' },
    capacity: {
        label: 'Organizational Capacity',
        tagline: 'People · Technology · Culture',
    },
}

/** Extra padding below the bottom band so the canvas border doesn't crowd the last chip. */
const CANVAS_BOTTOM_PADDING = 32

/**
 * React Flow canvas hosting the four-band strategy-map graph.
 *
 * The canvas is interactive: pan, pinch-zoom on touch, tap-to-focus on
 * chips (which surfaces their tooltip via `selected` state). Edge hover
 * surfaces a popover with the cause-effect hypothesis text. Edges
 * default to low-opacity so chips read as primary content.
 *
 * Layout is computed by `buildStrategyMapGraph` once per
 * `strategyMap` value via `useMemo`. Edge styling is applied here
 * (rather than in the layout helper) so the data shape and the
 * presentation stay separate.
 */
export default function StrategyMapCanvas({ strategyMap }: { strategyMap: StrategyMap }) {
    // Ref on the canvas container so the edge tooltip can position itself
    // relative to the canvas (not the viewport). See `CanvasInner` —
    // tooltip positioning details + the scroll-tracking rationale.
    const canvasRef = useRef<HTMLDivElement | null>(null)

    const { nodes, edges, bands } = useMemo(() => {
        const graph = buildStrategyMapGraph(strategyMap)
        const styledEdges = graph.edges.map((edge) => ({
            ...edge,
            style: { stroke: 'var(--text-tertiary)', strokeWidth: 1.5, strokeOpacity: 0.45 },
            markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--text-tertiary)' },
        }))
        return { nodes: graph.nodes, edges: styledEdges, bands: graph.bands }
    }, [strategyMap])

    // Total label-row width = the rightmost x of any node + a chip's
    // worth of padding. Used by BandLabels to span the whole world
    // horizontally (so each band's label runs across all theme columns
    // + the shared lane).
    const labelRowWidth = useMemo(() => {
        if (nodes.length === 0) return COLUMN_WIDTH
        const maxX = Math.max(...nodes.map((node) => node.position.x))
        return maxX + COLUMN_WIDTH
    }, [nodes])

    // Canvas height grows with the band geometry. Replaces the old
    // ``4 * BAND_HEIGHT + 32`` constant — bands are now dynamic so the
    // total height must follow.
    const canvasHeight = useMemo(() => totalCanvasHeight(bands) + CANVAS_BOTTOM_PADDING, [bands])

    return (
        <div
            ref={canvasRef}
            data-testid="strategy-map-canvas"
            style={{
                position: 'relative',
                width: '100%',
                height: `${canvasHeight}px`,
                background: 'var(--bg-surface-2)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
            }}
        >
            <ReactFlowProvider>
                <CanvasInner
                    canvasRef={canvasRef}
                    nodes={nodes}
                    edges={edges}
                    bands={bands}
                    labelRowWidth={labelRowWidth}
                />
            </ReactFlowProvider>
        </div>
    )
}

function CanvasInner({
    canvasRef,
    nodes,
    edges,
    bands,
    labelRowWidth,
}: {
    canvasRef: React.RefObject<HTMLDivElement | null>
    nodes: Node<StrategyMapNodeData>[]
    edges: Edge<StrategyMapEdgeData>[]
    bands: StrategyMapBand[]
    labelRowWidth: number
}) {
    const [edgeTooltip, setEdgeTooltip] = useState<{ x: number; y: number; hypothesis: string } | null>(null)

    return (
        <>
            <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={NODE_TYPES}
                nodesDraggable={false}
                nodesConnectable={false}
                elementsSelectable
                fitView
                fitViewOptions={{ padding: 0.18 }}
                minZoom={0.5}
                maxZoom={1.5}
                proOptions={{ hideAttribution: true }}
                onEdgeMouseEnter={(event, edge) => {
                    const hypothesis = (edge.data as StrategyMapEdgeData | undefined)?.hypothesis
                    if (!hypothesis) return
                    // Position the tooltip relative to the canvas container,
                    // NOT the viewport. The previous implementation used
                    // `clientX/Y` + `position: fixed`, which left the tooltip
                    // viewport-pinned: if the user scrolled the page while
                    // hovering an edge, the edge moved with the scroll but
                    // the tooltip stayed put. By subtracting the canvas's
                    // bounding rect we get a coordinate that's stable inside
                    // an absolutely-positioned child of the canvas div.
                    const rect = canvasRef.current?.getBoundingClientRect()
                    setEdgeTooltip({
                        x: event.clientX - (rect?.left ?? 0),
                        y: event.clientY - (rect?.top ?? 0),
                        hypothesis,
                    })
                }}
                onEdgeMouseLeave={() => setEdgeTooltip(null)}
            >
                <Background color="var(--border-subtle)" gap={32} size={1} />
                {/*
                 * Band labels live INSIDE the React Flow viewport via
                 * ViewportPortal so they pan + zoom with the chips. The
                 * earlier implementation rendered them as absolute-positioned
                 * siblings of <ReactFlow> in the canvas div, which kept the
                 * labels stationary while React Flow's `fitView` translated
                 * the chip layer — even at default zoom the labels drifted
                 * away from the chip rows. Putting them in the viewport
                 * portal makes them part of the same transformed coordinate
                 * space as the nodes; `pointer-events: none` keeps the
                 * cursor's view of the chips unchanged.
                 */}
                <ViewportPortal>
                    <BandLabels bands={bands} rowWidth={labelRowWidth} />
                </ViewportPortal>
                <Controls position="bottom-right" showInteractive={false} />
            </ReactFlow>
            {edgeTooltip ? <EdgeTooltip {...edgeTooltip} /> : null}
        </>
    )
}

function EdgeTooltip({ x, y, hypothesis }: { x: number; y: number; hypothesis: string }) {
    return (
        <div
            data-testid="strategy-map-edge-tooltip"
            role="tooltip"
            style={{
                // Absolute positioning relative to the canvas container (which
                // is `position: relative`). Tooltip travels with the canvas
                // when the user scrolls the page; previously `position: fixed`
                // anchored to the viewport and mis-tracked on scroll.
                position: 'absolute',
                top: y + 12,
                left: x + 12,
                width: '280px',
                padding: '8px 10px',
                background: 'var(--bg-surface-3)',
                border: '1px solid var(--border-strong)',
                borderRadius: '8px',
                boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
                fontSize: '0.75rem',
                color: 'var(--text-secondary)',
                lineHeight: 1.6,
                zIndex: 1000,
                pointerEvents: 'none',
            }}
        >
            {hypothesis}
        </div>
    )
}

/**
 * Decorative band labels rendered INSIDE the React Flow viewport via
 * `<ViewportPortal>` so they pan + zoom with the chips. Each band gets
 * its own absolute-positioned label at the band's `top` in world
 * coordinates (driven by the dynamic geometry computed in
 * ``buildStrategyMapGraph``), with a dashed bottom-border that spans
 * the full label row width (= the rightmost chip's column + a column's
 * worth of padding).
 *
 * `aria-hidden` because the same labels are also encoded into each
 * chip's `perspective` field and the chip's `aria-label`; screen
 * readers don't need them twice. `pointer-events: none` so the labels
 * never intercept mouse events meant for chips or edges.
 */
function BandLabels({ bands, rowWidth }: { bands: StrategyMapBand[]; rowWidth: number }) {
    return (
        <div aria-hidden="true">
            {bands.map((band) => {
                const labels = PERSPECTIVE_LABELS[band.perspective]
                return (
                    <div
                        key={band.perspective}
                        style={{
                            position: 'absolute',
                            // World-coordinate positioning: label at the top
                            // of its band. ViewportPortal applies the React
                            // Flow viewport's transform (pan + zoom) on top.
                            top: band.top,
                            left: 0,
                            width: rowWidth,
                            height: band.height,
                            borderBottom: '1px dashed var(--border-subtle)',
                            padding: '4px 8px',
                            fontSize: '0.75rem',
                            fontWeight: 700,
                            color: 'var(--text-tertiary)',
                            textTransform: 'uppercase',
                            letterSpacing: '0.06em',
                            pointerEvents: 'none',
                        }}
                    >
                        {labels.label}
                        <span
                            style={{
                                marginLeft: '8px',
                                fontWeight: 400,
                                textTransform: 'none',
                                letterSpacing: 0,
                                color: 'var(--text-tertiary)',
                                opacity: 0.7,
                            }}
                        >
                            {labels.tagline}
                        </span>
                    </div>
                )
            })}
        </div>
    )
}
