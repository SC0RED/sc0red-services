'use client'

import { useMemo, useState, useCallback, useEffect } from 'react'
import {
    ReactFlow,
    type Node,
    type Edge,
    useNodesState,
    useEdgesState,
    ReactFlowProvider,
    Controls,
    useReactFlow,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from '@dagrejs/dagre'
import type { EbitdaNode } from '@/lib/types/api'
import EbitdaNodeComponent, { type EbitdaNodeData } from '@/components/EbitdaNodeComponent'

const nodeTypes = { ebitdaNode: EbitdaNodeComponent }

/* Dagre node dimensions — MUST be larger than the actual rendered node
   to prevent clipping. Actual nodes are minWidth 200, ~100-130px tall. */
const DAGRE_NODE_WIDTH = 290
const DAGRE_NODE_HEIGHT = 130

export function flattenNodes(nodes: EbitdaNode[], parentId: string | null = null): EbitdaNode[] {
    const flat: EbitdaNode[] = []
    for (const node of nodes) {
        flat.push({ ...node, parent_id: parentId })
        if (node.children?.length) {
            flat.push(...flattenNodes(node.children, node.id))
        }
    }
    return flat
}

function getLayoutedElements(nodes: Node[], edges: Edge[]) {
    const g = new dagre.graphlib.Graph()
    g.setDefaultEdgeLabel(() => ({}))
    g.setGraph({ rankdir: 'TB', nodesep: 80, ranksep: 110 })

    nodes.forEach((node) => {
        g.setNode(node.id, { width: DAGRE_NODE_WIDTH, height: DAGRE_NODE_HEIGHT })
    })
    edges.forEach((edge) => {
        g.setEdge(edge.source, edge.target)
    })

    dagre.layout(g)

    const layoutedNodes = nodes.map((node) => {
        const n = g.node(node.id)
        return {
            ...node,
            position: { x: n.x - DAGRE_NODE_WIDTH / 2, y: n.y - DAGRE_NODE_HEIGHT / 2 },
        }
    })

    return { nodes: layoutedNodes, edges }
}

interface EbitdaTreeProps {
    treeData: EbitdaNode[]
    opportunities: Array<{ title: string; value_lever?: string }>
}

function EbitdaTreeInner({ treeData, opportunities }: EbitdaTreeProps) {
    const [isExpanded, setIsExpanded] = useState(false)
    const { fitView } = useReactFlow()

    const layouted = useMemo(() => {
        const flatNodes = flattenNodes(treeData)
        const rfNodes: Node[] = flatNodes.map((n) => ({
            id: n.id,
            type: 'ebitdaNode',
            position: { x: 0, y: 0 },
            data: {
                label: n.label,
                type: n.type,
                valueRange: n.value_range,
                percentageOfParent: n.percentage_of_parent,
                description: n.description || '',
                linkedOpportunities: (n.linked_opportunity_indices || [])
                    .filter((i) => i >= 0 && i < opportunities.length)
                    .map((i) => ({
                        title: opportunities[i].title,
                        valueLever: opportunities[i].value_lever || '',
                    })),
            } as EbitdaNodeData,
        }))

        const rfEdges: Edge[] = flatNodes
            .filter((n) => n.parent_id)
            .map((n) => ({
                id: `${n.parent_id}-${n.id}`,
                source: n.parent_id!,
                target: n.id,
                style: { stroke: 'rgba(139, 154, 196, 0.3)', strokeWidth: 1.5 },
                animated: false,
            }))

        return getLayoutedElements(rfNodes, rfEdges)
    }, [treeData, opportunities])

    const [nodes, , onNodesChange] = useNodesState(layouted.nodes)
    const [edges, , onEdgesChange] = useEdgesState(layouted.edges)

    const toggleExpand = useCallback(() => {
        setIsExpanded((prev) => !prev)
    }, [])

    // Re-fit view when expanding/collapsing to use the new container size
    useEffect(() => {
        const timeout = setTimeout(() => {
            fitView({ padding: 0.25, duration: 300 })
        }, 350)
        return () => clearTimeout(timeout)
    }, [isExpanded, fitView])

    // Lock body scroll when expanded
    useEffect(() => {
        if (isExpanded) {
            document.body.style.overflow = 'hidden'
        } else {
            document.body.style.overflow = ''
        }
        return () => {
            document.body.style.overflow = ''
        }
    }, [isExpanded])

    return (
        <div style={{ position: 'relative' }}>
            <div
                className="ebitda-tree-container"
                style={{
                    width: '100%',
                    height: isExpanded ? '100vh' : '700px',
                    borderRadius: isExpanded ? '0' : 'var(--radius-md, 8px)',
                    background: isExpanded ? '#060A12' : 'rgba(6, 10, 18, 0.5)',
                    transition: 'height 0.3s ease',
                    position: isExpanded ? 'fixed' : 'relative',
                    inset: isExpanded ? '0' : 'auto',
                    zIndex: isExpanded ? 1000 : 'auto',
                }}
            >
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    nodeTypes={nodeTypes}
                    nodesDraggable={false}
                    fitView
                    fitViewOptions={{ padding: 0.25, minZoom: 0.5, maxZoom: 1 }}
                    proOptions={{ hideAttribution: true }}
                    minZoom={0.3}
                    maxZoom={2.5}
                    panOnDrag
                    panOnScroll
                    zoomOnPinch
                    zoomOnDoubleClick
                    style={{ background: 'transparent' }}
                >
                    <Controls showInteractive={false} />
                </ReactFlow>

                {/* Top-right control buttons */}
                <div
                    style={{
                        position: 'absolute',
                        top: '0.75rem',
                        right: '0.75rem',
                        zIndex: 10,
                        display: 'flex',
                        gap: '0.5rem',
                    }}
                >
                    <button
                        onClick={() => fitView({ padding: 0.25, duration: 300 })}
                        style={{
                            padding: '0.375rem 0.75rem',
                            background: 'rgba(59, 123, 246, 0.15)',
                            border: '1px solid rgba(59, 123, 246, 0.3)',
                            borderRadius: '6px',
                            color: '#3B7BF6',
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.375rem',
                        }}
                    >
                        <svg
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                        >
                            <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
                        </svg>
                        Fit
                    </button>
                    <button
                        onClick={toggleExpand}
                        style={{
                            padding: '0.375rem 0.75rem',
                            background: isExpanded ? 'rgba(239, 68, 68, 0.15)' : 'rgba(59, 123, 246, 0.15)',
                            border: `1px solid ${isExpanded ? 'rgba(239, 68, 68, 0.3)' : 'rgba(59, 123, 246, 0.3)'}`,
                            borderRadius: '6px',
                            color: isExpanded ? '#EF4444' : '#3B7BF6',
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.375rem',
                        }}
                    >
                        <svg
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                        >
                            {isExpanded ? (
                                <path d="M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7" />
                            ) : (
                                <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
                            )}
                        </svg>
                        {isExpanded ? 'Close' : 'Expand'}
                    </button>
                </div>
            </div>

            {!isExpanded && (
                <div
                    style={{
                        textAlign: 'center',
                        marginTop: '0.5rem',
                        fontSize: '0.75rem',
                        color: 'var(--text-tertiary)',
                    }}
                >
                    Scroll to pan, pinch or use controls to zoom. Hover nodes for details.
                </div>
            )}
        </div>
    )
}

export default function EbitdaTree(props: EbitdaTreeProps) {
    return (
        <ReactFlowProvider>
            <EbitdaTreeInner {...props} />
        </ReactFlowProvider>
    )
}
