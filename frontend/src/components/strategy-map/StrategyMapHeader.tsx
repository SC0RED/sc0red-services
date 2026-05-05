'use client'

import { useState, type ReactNode } from 'react'

import type { StrategyMap } from '@/lib/types/api'
import { formatValueProposition } from '@/lib/utils/strategyMapUtils'

/**
 * Header band rendered above the strategy-map canvas.
 *
 * - **Vision**: italic single line, truncated with ellipsis. The full
 *   text is exposed via the native `title` attribute (browser tooltip)
 *   on overflow.
 * - **Mission**, **Value Proposition**, **Strategic Priorities**: each
 *   rendered with the same `ExpandableSection` disclosure pattern:
 *   uppercase section label as the summary, click toggles open/close,
 *   detail content (statement / chip + rationale / per-priority
 *   highlighted name + result text) lives in the body.
 *
 *   Earlier versions used three different interaction patterns
 *   (Mission as <details>, Value Proposition as a chip with hover
 *   tooltip, Strategic Priorities as pills with hover tooltips), which
 *   made the header feel inconsistent. Unifying on one disclosure
 *   pattern gives the user a single mental model and surfaces all
 *   detail with a click rather than a hover hunt.
 */
export default function StrategyMapHeader({ strategyMap }: { strategyMap: StrategyMap }) {
    const { vision, mission, valueProposition, strategicPriorities } = strategyMap
    const valueLabel = formatValueProposition(valueProposition.primary, valueProposition.secondary)
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

            <ExpandableSection label={`Mission${mission.synthesised ? ' (synthesised)' : ''}`}>
                <p style={bodyParagraphStyle}>{mission.statement}</p>
            </ExpandableSection>

            <ExpandableSection label="Value Proposition">
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <span style={valuePropositionChipStyle}>{valueLabel}</span>
                    <p style={bodyParagraphStyle}>{valueProposition.rationale}</p>
                </div>
            </ExpandableSection>

            {strategicPriorities.length > 0 ? (
                <ExpandableSection label="Strategic Priorities">
                    <ul
                        style={{
                            listStyle: 'none',
                            padding: 0,
                            margin: 0,
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '10px',
                        }}
                    >
                        {strategicPriorities.map((priority) => (
                            <li key={priority.name} style={priorityItemStyle}>
                                <h4 style={priorityNameStyle}>{priority.name}</h4>
                                <p style={bodyParagraphStyle}>{priority.result}</p>
                            </li>
                        ))}
                    </ul>
                </ExpandableSection>
            ) : null}
        </header>
    )
}

/**
 * One disclosure section in the header band. Uses native `<details>` so
 * the keyboard story is correct by default (`Enter`/`Space` toggles,
 * `aria-expanded` is implied). The native triangle marker is replaced
 * with a custom rotating ▸ that flips to ▾ on open — driven by React
 * state because inline styles can't target the `[open]` attribute.
 *
 * Default state is OPEN: the previous design had Mission collapsed and
 * the other two open, which forced the user to click to read the
 * mission. With the unified pattern we want the user to see all the
 * positioning content on first load; they can collapse anything
 * deliberately if they want a tighter view.
 */
function ExpandableSection({
    label,
    children,
    defaultOpen = true,
}: {
    label: string
    children: ReactNode
    defaultOpen?: boolean
}) {
    const [open, setOpen] = useState(defaultOpen)
    return (
        <details
            open={open}
            onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}
            style={{ fontSize: '0.85rem' }}
        >
            <summary style={summaryStyle}>
                <span
                    aria-hidden="true"
                    style={{
                        display: 'inline-block',
                        color: 'var(--accent-blue)',
                        transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
                        transition: 'transform 0.15s ease',
                        // Counteract the rotation visually so ▸ (right) → ▾ (down).
                        // Using a CSS rotate keeps a single character + animation
                        // while the underlying glyph stays a right-pointing arrow.
                        marginRight: '6px',
                        fontSize: '0.6rem',
                    }}
                >
                    ▶
                </span>
                {label}
            </summary>
            <div style={{ marginTop: '8px' }}>{children}</div>
        </details>
    )
}

// ── Shared styles for header section bodies ──────────────────────────

const summaryStyle: React.CSSProperties = {
    cursor: 'pointer',
    fontSize: '0.7rem',
    color: 'var(--text-tertiary)',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    listStyle: 'none', // hide native triangle so our custom marker is the only one
    display: 'inline-flex',
    alignItems: 'center',
    width: 'fit-content',
}

const bodyParagraphStyle: React.CSSProperties = {
    margin: 0,
    fontSize: '0.85rem',
    color: 'var(--text-secondary)',
    lineHeight: 1.6,
}

const valuePropositionChipStyle: React.CSSProperties = {
    display: 'inline-flex',
    width: 'fit-content',
    padding: '3px 10px',
    borderRadius: '999px',
    fontSize: '0.75rem',
    fontWeight: 700,
    background: 'var(--accent-blue-glow)',
    color: 'var(--accent-blue)',
    border: '1px solid var(--accent-blue)',
    letterSpacing: '0.02em',
}

const priorityItemStyle: React.CSSProperties = {
    paddingLeft: '12px',
    borderLeft: '3px solid var(--accent-blue)',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
}

const priorityNameStyle: React.CSSProperties = {
    margin: 0,
    fontSize: '0.85rem',
    fontWeight: 700,
    color: 'var(--text-primary)',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
}
