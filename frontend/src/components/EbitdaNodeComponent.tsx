'use client'

import { useState } from 'react'

import ConfidenceIndicator from '@/components/analysis/ConfidenceIndicator'
import { LEVER_COLORS } from '@/lib/utils/leverColors'

/**
 * Single P&L line-item card used by the EBITDA Impact Model section.
 *
 * Renders one of:
 *   - A *subtotal* card (Total Revenue, Cost of Revenue, Gross Profit,
 *     Operating Expenses, EBITDA) — sits in the centre of the
 *     waterfall column.
 *   - A *leaf* card (e.g. Subscriptions under Total Revenue) — flanks
 *     its parent subtotal on the right (desktop) or stacks below
 *     (mobile) per ``ebitda-impact-model`` Requirement 3.
 *
 * Visual treatment is unchanged from the pre-Phase-4 React-Flow node
 * (label, value range, percentage-of-parent, confidence chip,
 * opportunity dots, hover description). The structural change is
 * that the component is now a plain ``<article>`` — no
 * ``@xyflow/react`` ``Handle`` / ``Position`` plumbing — so it
 * renders in any container without a ``ReactFlowProvider`` parent.
 *
 * The component name is retained for diff hygiene; semantically this
 * is now an EBITDA *card*, not a graph node.
 */
export interface EbitdaCardProps {
    label: string
    type: 'revenue' | 'cost' | 'margin' | 'subtotal'
    valueRange?: string
    percentageOfParent?: number
    description: string
    linkedOpportunities: Array<{ title: string; valueLever: string }>
    /** Derivation-provenance level emitted by the backend. ``null`` /
     *  undefined suppresses the chip (no "unknown" badge — silence is
     *  more honest). */
    confidenceLevel?: 'high' | 'medium' | 'low' | null
    /** Human-readable explanation of which build inputs drove the
     *  figure; surfaced as a native ``title`` tooltip on the chip. */
    confidenceBasis?: string | null
    /** When ``true`` the label renders inside an ``<h3>`` so screen
     *  readers can navigate between the five P&L subtotals by heading.
     *  Per ``ebitda-impact-model`` Requirement §6. Leaves render the
     *  label in a non-heading element so the heading scale isn't
     *  polluted with up to ~12 driver rows. Defaults to ``false``. */
    isSubtotalHeading?: boolean
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

export default function EbitdaNodeComponent(props: EbitdaCardProps) {
    const [hovered, setHovered] = useState(false)
    const colors = NODE_COLORS[props.type] || NODE_COLORS.margin

    // Show a confidence chip when the backend supplied a level AND this is a
    // leaf (revenue/cost) node. Subtotal / margin rollups carry no own
    // confidence per the ebitda-tree-confidence spec — they inherit visually
    // via their children's chips.
    const showConfidenceChip =
        (props.confidenceLevel === 'high' ||
            props.confidenceLevel === 'medium' ||
            props.confidenceLevel === 'low') &&
        props.type !== 'subtotal' &&
        props.type !== 'margin'

    return (
        /* eslint-disable-next-line jsx-a11y/no-static-element-interactions */
        <article
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
                padding: '0.875rem 1.125rem',
                background: colors.bg,
                border: `1.5px solid ${hovered ? colors.text : colors.border}`,
                borderRadius: '10px',
                minWidth: '200px',
                position: 'relative',
                boxShadow: hovered
                    ? `0 0 30px ${colors.glow}, 0 4px 20px rgba(0,0,0,0.3)`
                    : `0 0 20px ${colors.glow}`,
                backdropFilter: 'blur(8px)',
            }}
        >
            {props.isSubtotalHeading ? (
                <h3 style={labelStyle(colors.text)}>{props.label}</h3>
            ) : (
                <div style={labelStyle(colors.text)}>{props.label}</div>
            )}
            {props.valueRange && (
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
                    <span>{props.valueRange}</span>
                    {showConfidenceChip && props.confidenceLevel && (
                        <span
                            data-testid="ebitda-confidence-chip"
                            tabIndex={0}
                            // Native HTML title gives a hover/focus tooltip
                            // for free; ConfidenceIndicator's own aria-label
                            // still provides the level to screen readers.
                            title={props.confidenceBasis ?? undefined}
                            style={{ display: 'inline-flex', cursor: 'help' }}
                        >
                            <ConfidenceIndicator
                                confidence={props.confidenceLevel.toUpperCase() as 'HIGH' | 'MEDIUM' | 'LOW'}
                                size="small"
                            />
                        </span>
                    )}
                </div>
            )}
            {props.percentageOfParent != null && (
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    {props.percentageOfParent}% of parent
                </div>
            )}

            {props.linkedOpportunities.length > 0 && (
                <div
                    data-testid="ebitda-linked-opportunity-dots"
                    style={{ display: 'flex', gap: '4px', marginTop: '0.5rem', flexWrap: 'wrap' }}
                >
                    {props.linkedOpportunities.map((opp, i) => (
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

            {hovered && props.description && (
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
                    <div style={{ marginBottom: '0.375rem' }}>{props.description}</div>
                    {props.linkedOpportunities.length > 0 && (
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
                            {props.linkedOpportunities.map((opp, i) => (
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
        </article>
    )
}

/** Shared style for the card's label so the ``<h3>`` vs ``<div>``
 *  branch (driven by ``isSubtotalHeading``) doesn't drift visually.
 *  The browser's default ``<h3>`` margins are stripped here. */
function labelStyle(textColor: string): React.CSSProperties {
    return {
        fontWeight: 700,
        fontSize: '0.9375rem',
        color: textColor,
        marginTop: 0,
        marginBottom: '0.375rem',
    }
}
