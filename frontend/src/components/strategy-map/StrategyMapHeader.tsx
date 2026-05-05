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
 *   rendered with the same `ExpandableSection` disclosure pattern as
 *   the gaps in `WhatsMissingPanel` — single-open accordion, all
 *   closed by default, click a header to expand its detail (and
 *   collapse any other open header). One mental model across the
 *   entire strategy-map section: header rows are compact summaries,
 *   click to drill in.
 */
type HeaderSectionId = 'mission' | 'value-proposition' | 'strategic-priorities'

export default function StrategyMapHeader({ strategyMap }: { strategyMap: StrategyMap }) {
    const { vision, mission, valueProposition, strategicPriorities } = strategyMap
    const valueLabel = formatValueProposition(valueProposition.primary, valueProposition.secondary)

    // Single-open accordion: at most one section expanded at any time.
    // Mirrors `WhatsMissingPanel`'s `expandedGapId` pattern so the user
    // sees the same interaction on both sides of the canvas.
    const [openSection, setOpenSection] = useState<HeaderSectionId | null>(null)
    const toggle = (id: HeaderSectionId) => setOpenSection((current) => (current === id ? null : id))

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

            <ExpandableSection
                label={`Mission${mission.synthesised ? ' (synthesised)' : ''}`}
                isOpen={openSection === 'mission'}
                onToggle={() => toggle('mission')}
            >
                <p style={bodyParagraphStyle}>{mission.statement}</p>
            </ExpandableSection>

            <ExpandableSection
                label="Value Proposition"
                isOpen={openSection === 'value-proposition'}
                onToggle={() => toggle('value-proposition')}
            >
                {/*
                 * Same left-bar header treatment as each strategic priority
                 * below — both are highlighted identity claims for the
                 * company, both render with one consistent shape: blue
                 * accent left border + uppercase title + paragraph
                 * underneath. The earlier pill-chip treatment for the
                 * value-proposition classification didn't read as a
                 * "header" the way left-bar uppercase does.
                 */}
                <LabelledItem name={valueLabel}>{valueProposition.rationale}</LabelledItem>
            </ExpandableSection>

            {strategicPriorities.length > 0 ? (
                <ExpandableSection
                    label="Strategic Priorities"
                    isOpen={openSection === 'strategic-priorities'}
                    onToggle={() => toggle('strategic-priorities')}
                >
                    <ul
                        style={{
                            listStyle: 'none',
                            padding: 0,
                            margin: 0,
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '12px',
                        }}
                    >
                        {strategicPriorities.map((priority) => (
                            <li key={priority.name}>
                                <LabelledItem name={priority.name}>{priority.result}</LabelledItem>
                            </li>
                        ))}
                    </ul>
                </ExpandableSection>
            ) : null}
        </header>
    )
}

/**
 * Controlled disclosure section. The parent owns `isOpen` so single-open
 * accordion behaviour can be enforced across siblings — exactly the
 * pattern used by `WhatsMissingPanel`'s `GapRow`.
 *
 * Built on native `<details>` for accessibility-by-default. The summary
 * click is intercepted (`event.preventDefault()` blocks the browser's
 * native open/close) so the toggle goes through React state and stays
 * authoritative — without the intercept the browser would also flip
 * the `open` attribute and React's controlled `open` prop would
 * disagree with the DOM.
 */
function ExpandableSection({
    label,
    isOpen,
    onToggle,
    children,
}: {
    label: string
    isOpen: boolean
    onToggle: () => void
    children: ReactNode
}) {
    return (
        <details open={isOpen} style={{ fontSize: '0.85rem' }}>
            <summary
                onClick={(event) => {
                    event.preventDefault()
                    onToggle()
                }}
                aria-expanded={isOpen}
                style={summaryStyle}
            >
                <span
                    aria-hidden="true"
                    style={{
                        display: 'inline-block',
                        color: 'var(--accent-blue)',
                        transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)',
                        transition: 'transform 0.15s ease',
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

/**
 * Shared block layout for any "highlighted identity claim" in the
 * header — the value-proposition classification + each strategic
 * priority. Blue accent left border + uppercase heading + paragraph
 * detail underneath. One consistent treatment regardless of which
 * disclosure section the item lives in.
 */
function LabelledItem({ name, children }: { name: string; children: ReactNode }) {
    return (
        <div style={labelledItemStyle}>
            <h4 style={labelledItemHeadingStyle}>{name}</h4>
            <p style={bodyParagraphStyle}>{children}</p>
        </div>
    )
}

const labelledItemStyle: React.CSSProperties = {
    paddingLeft: '12px',
    borderLeft: '3px solid var(--accent-blue)',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
}

const labelledItemHeadingStyle: React.CSSProperties = {
    margin: 0,
    fontSize: '0.85rem',
    fontWeight: 700,
    color: 'var(--text-primary)',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
}
