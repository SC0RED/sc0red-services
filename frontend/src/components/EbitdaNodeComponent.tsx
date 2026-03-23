'use client'

import { useState } from 'react'
import { type Node, Position, Handle, type NodeProps } from '@xyflow/react'
import { LEVER_COLORS } from '@/lib/utils/leverColors'

export interface EbitdaNodeData extends Record<string, unknown> {
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

export default function EbitdaNodeComponent({ data }: NodeProps<Node<EbitdaNodeData>>) {
    const [hovered, setHovered] = useState(false)
    const colors = NODE_COLORS[data.type] || NODE_COLORS.margin

    return (
        /* eslint-disable-next-line jsx-a11y/no-static-element-interactions */
        <div
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
                padding: '0.875rem 1.125rem',
                background: colors.bg,
                border: `1.5px solid ${hovered ? colors.text : colors.border}`,
                borderRadius: '10px',
                minWidth: '200px',
                maxWidth: '280px',
                position: 'relative',
                boxShadow: hovered
                    ? `0 0 30px ${colors.glow}, 0 4px 20px rgba(0,0,0,0.3)`
                    : `0 0 20px ${colors.glow}`,
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
                    fontSize: '0.9375rem',
                    color: colors.text,
                    marginBottom: '0.375rem',
                }}
            >
                {data.label}
            </div>
            {data.valueRange && (
                <div
                    style={{
                        fontSize: '1rem',
                        fontWeight: 600,
                        color: '#EEF2FF',
                        marginBottom: '0.25rem',
                    }}
                >
                    {data.valueRange}
                </div>
            )}
            {data.percentageOfParent != null && (
                <div style={{ fontSize: '0.8125rem', color: '#8B9AC4' }}>
                    {data.percentageOfParent}% of parent
                </div>
            )}

            {data.linkedOpportunities.length > 0 && (
                <div style={{ display: 'flex', gap: '4px', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                    {data.linkedOpportunities.map((opp, i) => (
                        <div
                            key={i}
                            style={{
                                width: '10px',
                                height: '10px',
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
                        padding: '0.75rem 0.875rem',
                        background: '#1A2538',
                        border: '1px solid rgba(59,123,246,0.25)',
                        borderRadius: '8px',
                        fontSize: '0.8125rem',
                        color: '#EEF2FF',
                        width: '260px',
                        zIndex: 50,
                        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
                        lineHeight: 1.6,
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
                                    fontSize: '0.75rem',
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
                                        marginBottom: '0.25rem',
                                    }}
                                >
                                    <div
                                        style={{
                                            width: '7px',
                                            height: '7px',
                                            borderRadius: '50%',
                                            flexShrink: 0,
                                            background: LEVER_COLORS[opp.valueLever] || '#8B9AC4',
                                        }}
                                    />
                                    <span style={{ fontSize: '0.75rem' }}>{opp.title}</span>
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
