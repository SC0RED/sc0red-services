'use client'

import { useState } from 'react'
import { type Node, Position, Handle, type NodeProps } from '@xyflow/react'
import ConfidenceIndicator from '@/components/analysis/ConfidenceIndicator'
import { LEVER_COLORS } from '@/lib/utils/leverColors'

export interface EbitdaNodeData extends Record<string, unknown> {
    label: string
    type: 'revenue' | 'cost' | 'margin' | 'subtotal'
    valueRange?: string
    percentageOfParent?: number
    description: string
    linkedOpportunities: Array<{ title: string; valueLever: string }>
    /** Derivation-provenance level emitted by the backend. `null` / undefined
     *  suppresses the chip (no "unknown" badge — silence is more honest). */
    confidenceLevel?: 'high' | 'medium' | 'low' | null
    /** Human-readable explanation of which build inputs drove the figure;
     *  surfaced as a tooltip below the chip. */
    confidenceBasis?: string | null
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

    // Show a confidence chip when the backend supplied a level AND this is a
    // leaf (revenue/cost) node. Subtotal / margin rollups carry no own
    // confidence per the ebitda-tree-confidence spec — they inherit visually
    // via their children's chips.
    const showConfidenceChip =
        (data.confidenceLevel === 'high' ||
            data.confidenceLevel === 'medium' ||
            data.confidenceLevel === 'low') &&
        data.type !== 'subtotal' &&
        data.type !== 'margin'

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
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        fontSize: '1rem',
                        fontWeight: 600,
                        color: 'var(--text-primary)',
                        marginBottom: '0.25rem',
                    }}
                >
                    <span>{data.valueRange}</span>
                    {showConfidenceChip && data.confidenceLevel && (
                        <span
                            data-testid="ebitda-confidence-chip"
                            tabIndex={0}
                            // Native HTML title gives a hover/focus tooltip for
                            // free; ConfidenceIndicator's own aria-label still
                            // provides the level to screen readers. Using
                            // `title` keeps us within the node's React-Flow
                            // bounds (no portal) so the tooltip doesn't get
                            // clipped by the flow container.
                            title={data.confidenceBasis ?? undefined}
                            style={{ display: 'inline-flex', cursor: 'help' }}
                        >
                            <ConfidenceIndicator
                                confidence={data.confidenceLevel.toUpperCase() as 'HIGH' | 'MEDIUM' | 'LOW'}
                                size="small"
                            />
                        </span>
                    )}
                </div>
            )}
            {data.percentageOfParent != null && (
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
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
                                background: LEVER_COLORS[opp.valueLever] || 'var(--text-secondary)',
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
                        background: 'var(--bg-surface-3)',
                        border: '1px solid var(--border-strong)',
                        borderRadius: '8px',
                        fontSize: '0.8125rem',
                        color: 'var(--text-primary)',
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
                                    color: 'var(--text-secondary)',
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
                                            background:
                                                LEVER_COLORS[opp.valueLever] || 'var(--text-secondary)',
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
