'use client'

import { useState } from 'react'

import type { StrategyMap } from '@/lib/types/api'
import { formatValueProposition } from '@/lib/utils/strategyMapUtils'

/**
 * Header band rendered above the strategy-map canvas.
 *
 * - **Vision**: italic single line, truncated with ellipsis. The full
 *   text is exposed via the native `title` attribute (browser tooltip)
 *   on overflow.
 * - **Mission**: hidden behind a native `<details>` disclosure
 *   (`Mission ▾`). Closed by default.
 * - **Value proposition**: chip stays visible; rationale moves into a
 *   hover/focus tooltip on the chip.
 * - **Strategic priorities**: pill list with hover/focus tooltip
 *   surfacing the priority's `result` text.
 */
export default function StrategyMapHeader({ strategyMap }: { strategyMap: StrategyMap }) {
    const { vision, mission, valueProposition, strategicPriorities } = strategyMap
    return (
        <header
            style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                paddingBottom: '12px',
                borderBottom: '1px solid var(--border-subtle)',
            }}
        >
            <div
                style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    color: 'var(--accent-blue)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                }}
            >
                Strategy Map
            </div>

            <p
                title={vision.statement}
                style={{
                    fontSize: '1rem',
                    fontStyle: 'italic',
                    color: 'var(--text-primary)',
                    lineHeight: 1.4,
                    margin: 0,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                }}
            >
                &ldquo;{vision.statement}&rdquo;
                {vision.synthesised ? (
                    <span
                        style={{
                            marginLeft: '8px',
                            fontStyle: 'normal',
                            fontSize: '0.7rem',
                            color: 'var(--text-tertiary)',
                            fontWeight: 600,
                            letterSpacing: '0.06em',
                            textTransform: 'uppercase',
                        }}
                    >
                        (synthesised)
                    </span>
                ) : null}
            </p>

            <details style={{ fontSize: '0.85rem' }}>
                <summary
                    style={{
                        cursor: 'pointer',
                        fontSize: '0.7rem',
                        color: 'var(--text-tertiary)',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                    }}
                >
                    Mission {mission.synthesised ? '(synthesised)' : ''}
                </summary>
                <p
                    style={{
                        fontSize: '0.9rem',
                        color: 'var(--text-secondary)',
                        margin: '8px 0 0',
                        lineHeight: 1.6,
                    }}
                >
                    {mission.statement}
                </p>
            </details>

            <ValuePropositionRow valueProposition={valueProposition} />

            {strategicPriorities.length > 0 ? <PriorityLegend priorities={strategicPriorities} /> : null}
        </header>
    )
}

function ValuePropositionRow({ valueProposition }: { valueProposition: StrategyMap['valueProposition'] }) {
    const [hovered, setHovered] = useState(false)
    const label = formatValueProposition(valueProposition.primary, valueProposition.secondary)
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', position: 'relative' }}>
            <span
                style={{
                    fontSize: '0.7rem',
                    color: 'var(--text-tertiary)',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                }}
            >
                Value Proposition:
            </span>
            <button
                type="button"
                onMouseEnter={() => setHovered(true)}
                onMouseLeave={() => setHovered(false)}
                onFocus={() => setHovered(true)}
                onBlur={() => setHovered(false)}
                onClick={() => setHovered((current) => !current)}
                aria-describedby={hovered ? 'value-prop-rationale' : undefined}
                style={{
                    display: 'inline-flex',
                    padding: '3px 10px',
                    borderRadius: '999px',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    background: 'var(--accent-blue-glow)',
                    color: 'var(--accent-blue)',
                    border: '1px solid var(--accent-blue)',
                    letterSpacing: '0.02em',
                    cursor: 'help',
                    fontFamily: 'inherit',
                }}
            >
                {label}
            </button>
            {hovered ? (
                <div
                    id="value-prop-rationale"
                    role="tooltip"
                    style={{
                        position: 'absolute',
                        top: '100%',
                        left: 0,
                        marginTop: '6px',
                        maxWidth: '480px',
                        padding: '10px 12px',
                        background: 'var(--bg-surface-3)',
                        border: '1px solid var(--border-strong)',
                        borderRadius: '8px',
                        boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
                        fontSize: '0.78rem',
                        color: 'var(--text-secondary)',
                        lineHeight: 1.6,
                        zIndex: 10,
                    }}
                >
                    {valueProposition.rationale}
                </div>
            ) : null}
        </div>
    )
}

function PriorityLegend({ priorities }: { priorities: StrategyMap['strategicPriorities'] }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div
                style={{
                    fontSize: '0.7rem',
                    color: 'var(--text-tertiary)',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                }}
            >
                Strategic Priorities
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {priorities.map((priority) => (
                    <PriorityPill key={priority.name} priority={priority} />
                ))}
            </div>
        </div>
    )
}

function PriorityPill({ priority }: { priority: StrategyMap['strategicPriorities'][number] }) {
    const [hovered, setHovered] = useState(false)
    const tooltipId = `priority-${priority.name.replace(/\s+/g, '-')}`
    return (
        <button
            type="button"
            aria-describedby={hovered ? tooltipId : undefined}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            onFocus={() => setHovered(true)}
            onBlur={() => setHovered(false)}
            onClick={() => setHovered((current) => !current)}
            style={{
                position: 'relative',
                padding: '4px 10px',
                borderRadius: '6px',
                background: 'var(--bg-surface-2)',
                borderTop: '3px solid var(--accent-blue)',
                borderRight: '1px solid transparent',
                borderBottom: '1px solid transparent',
                borderLeft: '1px solid transparent',
                fontSize: '0.78rem',
                fontWeight: 600,
                color: 'var(--text-primary)',
                cursor: 'help',
                fontFamily: 'inherit',
                textAlign: 'left',
            }}
        >
            {priority.name}
            {hovered ? (
                <span
                    id={tooltipId}
                    role="tooltip"
                    style={{
                        position: 'absolute',
                        top: '100%',
                        left: 0,
                        marginTop: '6px',
                        width: '280px',
                        padding: '10px 12px',
                        background: 'var(--bg-surface-3)',
                        border: '1px solid var(--border-strong)',
                        borderRadius: '8px',
                        boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
                        fontSize: '0.75rem',
                        fontWeight: 400,
                        color: 'var(--text-secondary)',
                        lineHeight: 1.6,
                        zIndex: 10,
                        whiteSpace: 'normal',
                    }}
                >
                    {priority.result}
                </span>
            ) : null}
        </button>
    )
}
