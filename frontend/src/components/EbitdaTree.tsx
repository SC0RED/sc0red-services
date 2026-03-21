'use client'

import { useMemo, useState } from 'react'
import {
    ReactFlow,
    type Node,
    type Edge,
    Position,
    Handle,
    useNodesState,
    useEdgesState,
    type NodeProps,
    ReactFlowProvider,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from '@dagrejs/dagre'
import { LEVER_COLORS } from '@/lib/utils/leverColors'
import type { EbitdaNode } from '@/lib/types/api'

interface EbitdaNodeData extends Record<string, unknown> {
    label: string
    type: 'revenue' | 'cost' | 'margin' | 'subtotal'
    valueRange?: string
    percentageOfParent?: number
    description: string
    linkedOpportunities: Array<{ title: string; valueLever: string }>
}

const NODE_COLORS: Record<string, { bg: string; border: string; text: string; glow: string }> = {
    revenue: {
        bg: 'rgba(34, 197, 94, 0.12)',
        border: 'rgba(34, 197, 94, 0.4)',
        text: '#22C55E',
        glow: 'rgba(34, 197, 94, 0.15)',
    },
    cost: {
        bg: 'rgba(239, 68, 68, 0.12)',
        border: 'rgba(239, 68, 68, 0.4)',
        text: '#EF4444',
        glow: 'rgba(239, 68, 68, 0.15)',
    },
    margin: {
        bg: 'rgba(59, 123, 246, 0.12)',
        border: 'rgba(59, 123, 246, 0.4)',
        text: '#3B7BF6',
        glow: 'rgba(59, 123, 246, 0.15)',
    },
    subtotal: {
        bg: 'rgba(245, 158, 11, 0.12)',
        border: 'rgba(245, 158, 11, 0.4)',
        text: '#F59E0B',
        glow: 'rgba(245, 158, 11, 0.15)',
    },
}

function EbitdaNodeComponent({ data }: NodeProps<Node<EbitdaNodeData>>) {
    const [hovered, setHovered] = useState(false)
    const colors = NODE_COLORS[data.type] || NODE_COLORS.margin

    return (
        <div
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
                padding: '0.75rem 1rem',
                background: colors.bg,
                border: `1.5px solid ${colors.border}`,
                borderRadius: '10px',
                minWidth: '180px',
                maxWidth: '240px',
                position: 'relative',
                boxShadow: `0 0 20px ${colors.glow}`,
                backdropFilter: 'blur(8px)',
            }}
        >
            <Handle
                type="target"
                position={Position.Top}
                style={{ background: colors.border, border: 'none', width: 8, height: 8 }}
            />

            <div
                style={{
                    fontWeight: 700,
                    fontSize: '0.8125rem',
                    color: colors.text,
                    marginBottom: '0.25rem',
                }}
            >
                {data.label}
            </div>
            {data.valueRange && (
                <div
                    style={{
                        fontSize: '0.875rem',
                        fontWeight: 600,
                        color: '#EEF2FF',
                        marginBottom: '0.125rem',
                    }}
                >
                    {data.valueRange}
                </div>
            )}
            {data.percentageOfParent != null && (
                <div style={{ fontSize: '0.6875rem', color: '#8B9AC4' }}>
                    {data.percentageOfParent}% of parent
                </div>
            )}

            {data.linkedOpportunities.length > 0 && (
                <div style={{ display: 'flex', gap: '3px', marginTop: '0.375rem', flexWrap: 'wrap' }}>
                    {data.linkedOpportunities.map((opp, i) => (
                        <div
                            key={i}
                            style={{
                                width: '8px',
                                height: '8px',
                                borderRadius: '50%',
                                background: LEVER_COLORS[opp.valueLever] || '#8B9AC4',
                            }}
                            title={`${opp.title} (${opp.valueLever})`}
                        />
                    ))}
                </div>
            )}

            {hovered && data.description && (
                <div
                    style={{
                        position: 'absolute',
                        top: '100%',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        marginTop: '8px',
                        padding: '0.625rem 0.75rem',
                        background: '#1A2538',
                        border: '1px solid rgba(59,123,246,0.25)',
                        borderRadius: '8px',
                        fontSize: '0.75rem',
                        color: '#EEF2FF',
                        width: '220px',
                        zIndex: 50,
                        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
                        lineHeight: 1.5,
                    }}
                >
                    <div style={{ marginBottom: '0.375rem' }}>{data.description}</div>
                    {data.linkedOpportunities.length > 0 && (
                        <div
                            style={{
                                borderTop: '1px solid rgba(255,255,255,0.06)',
                                paddingTop: '0.375rem',
                                marginTop: '0.25rem',
                            }}
                        >
                            <div
                                style={{
                                    fontSize: '0.6875rem',
                                    color: '#8B9AC4',
                                    fontWeight: 600,
                                    marginBottom: '0.25rem',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.05em',
                                }}
                            >
                                AI Opportunities
                            </div>
                            {data.linkedOpportunities.map((opp, i) => (
                                <div
                                    key={i}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '0.375rem',
                                        marginBottom: '0.125rem',
                                    }}
                                >
                                    <div
                                        style={{
                                            width: '6px',
                                            height: '6px',
                                            borderRadius: '50%',
                                            flexShrink: 0,
                                            background: LEVER_COLORS[opp.valueLever] || '#8B9AC4',
                                        }}
                                    />
                                    <span style={{ fontSize: '0.6875rem' }}>{opp.title}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            <Handle
                type="source"
                position={Position.Bottom}
                style={{ background: colors.border, border: 'none', width: 8, height: 8 }}
            />
        </div>
    )
}

const nodeTypes = { ebitdaNode: EbitdaNodeComponent }

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
    g.setGraph({ rankdir: 'TB', nodesep: 40, ranksep: 80 })

    nodes.forEach((node) => {
        g.setNode(node.id, { width: 200, height: 80 })
    })
    edges.forEach((edge) => {
        g.setEdge(edge.source, edge.target)
    })

    dagre.layout(g)

    const layoutedNodes = nodes.map((node) => {
        const n = g.node(node.id)
        return { ...node, position: { x: n.x - 100, y: n.y - 40 } }
    })

    return { nodes: layoutedNodes, edges }
}

interface EbitdaTreeProps {
    treeData: EbitdaNode[]
    opportunities: Array<{ title: string; value_lever?: string }>
}

function EbitdaTreeInner({ treeData, opportunities }: EbitdaTreeProps) {
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

    return (
        <div
            style={{
                width: '100%',
                height: '500px',
                borderRadius: 'var(--radius-md, 8px)',
                overflow: 'hidden',
                background: 'rgba(6, 10, 18, 0.5)',
            }}
        >
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                nodeTypes={nodeTypes}
                fitView
                fitViewOptions={{ padding: 0.2 }}
                proOptions={{ hideAttribution: true }}
                minZoom={0.3}
                maxZoom={1.5}
                panOnDrag
                zoomOnScroll
                style={{ background: 'transparent' }}
            />
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
