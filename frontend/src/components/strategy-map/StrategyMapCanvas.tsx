'use client'

import { useMemo, useState } from 'react'
import {
    Background,
    Controls,
    type Edge,
    MarkerType,
    type Node,
    ReactFlow,
    ReactFlowProvider,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import {
    BAND_HEIGHT,
    type StrategyMapEdgeData,
    type StrategyMapNodeData,
    buildStrategyMapGraph,
} from '@/lib/strategyMap/layout'
import type { StrategyMap } from '@/lib/types/api'

import StrategyMapNode from './StrategyMapNode'

const NODE_TYPES = { strategyMap: StrategyMapNode }

const PERSPECTIVE_LABELS: ReadonlyArray<{ label: string; tagline: string }> = [
    { label: 'Financial', tagline: 'Returns we generate' },
    { label: 'Customer', tagline: 'What customers experience' },
    { label: 'Internal Processes', tagline: 'What we do operationally' },
    { label: 'Organizational Capacity', tagline: 'People · Technology · Culture' },
]

/** Default canvas height (4 bands × BAND_HEIGHT + a bit of padding). */
const CANVAS_HEIGHT = 4 * BAND_HEIGHT + 32

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
    const { nodes, edges } = useMemo(() => {
        const graph = buildStrategyMapGraph(strategyMap)
        const styledEdges = graph.edges.map((edge) => ({
            ...edge,
            style: { stroke: 'var(--text-tertiary)', strokeWidth: 1.5, strokeOpacity: 0.45 },
            markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--text-tertiary)' },
        }))
        return { nodes: graph.nodes, edges: styledEdges }
    }, [strategyMap])

    return (
        <div
            data-testid="strategy-map-canvas"
            style={{
                position: 'relative',
                width: '100%',
                height: `${CANVAS_HEIGHT}px`,
                background: 'var(--bg-surface-2)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
            }}
        >
            <BandLabels />
            <ReactFlowProvider>
                <CanvasInner nodes={nodes} edges={edges} />
            </ReactFlowProvider>
        </div>
    )
}

function CanvasInner({
    nodes,
    edges,
}: {
    nodes: Node<StrategyMapNodeData>[]
    edges: Edge<StrategyMapEdgeData>[]
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
                    setEdgeTooltip({ x: event.clientX, y: event.clientY, hypothesis })
                }}
                onEdgeMouseLeave={() => setEdgeTooltip(null)}
            >
                <Background color="var(--border-subtle)" gap={32} size={1} />
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
                position: 'fixed',
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
 * Decorative band labels rendered behind the canvas. Each band shows
 * its perspective name + tagline so users can read the canvas without
 * having to infer band identity from chip placement.
 *
 * `aria-hidden` because the same labels are also encoded into each
 * chip's `perspective` field and the chip's `aria-label`; screen
 * readers don't need them twice.
 */
function BandLabels() {
    return (
        <div
            aria-hidden="true"
            style={{
                position: 'absolute',
                inset: 0,
                pointerEvents: 'none',
                display: 'flex',
                flexDirection: 'column',
                zIndex: 1,
            }}
        >
            {PERSPECTIVE_LABELS.map((band) => (
                <div
                    key={band.label}
                    style={{
                        height: BAND_HEIGHT,
                        borderBottom: '1px dashed var(--border-subtle)',
                        padding: '4px 8px',
                        fontSize: '0.65rem',
                        fontWeight: 700,
                        color: 'var(--text-tertiary)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                    }}
                >
                    {band.label}
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
                        {band.tagline}
                    </span>
                </div>
            ))}
        </div>
    )
}
