'use client'

import { useState } from 'react'

import type { Gap } from '@/lib/types/api'

interface WhatsMissingPanelProps {
    gaps: Gap[]
}

/**
 * "What's Missing?" panel — the conversion engine of the strategy map.
 *
 * Per Kaplan & Norton's Mobil case study (HBR 2000): strategy maps
 * EXPOSE strategic gaps. Each generated map identifies 2-4 gaps
 * suitable for a deep-dive conversation. Each gap has its own
 * `deepDiveFraming` sentence describing what a Vector Advisory
 * engagement would specifically address.
 *
 * Renders gaps as a click-to-expand accordion (single-open, mirrors
 * `OpportunitiesList`'s pattern). Default state is collapsed: only the
 * gap ID and title are visible. Clicking a gap row expands it to show
 * the description and the deep-dive framing; clicking another gap
 * collapses the previously open one.
 *
 * The conversion path is: user scans the map → notices gaps relevant
 * to their portfolio → expands one to read the framing → clicks the
 * deep-dive CTA at the top of the analysis page.
 */
export default function WhatsMissingPanel({ gaps }: WhatsMissingPanelProps) {
    const [expandedGapId, setExpandedGapId] = useState<string | null>(null)

    if (gaps.length === 0) return null

    return (
        <section
            data-testid="strategy-map-whats-missing"
            style={{
                marginTop: '8px',
                padding: '14px 18px',
                background: 'var(--bg-surface-3)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
            }}
        >
            <header
                style={{
                    display: 'flex',
                    alignItems: 'baseline',
                    gap: '12px',
                    marginBottom: '10px',
                }}
            >
                <h3
                    style={{
                        fontSize: '0.95rem',
                        fontWeight: 700,
                        margin: 0,
                        color: 'var(--text-primary)',
                    }}
                >
                    What&rsquo;s Missing?
                </h3>
                <span
                    style={{
                        fontSize: '0.75rem',
                        color: 'var(--text-tertiary)',
                        fontStyle: 'italic',
                    }}
                >
                    Strategic gaps a deep-dive engagement would address
                </span>
            </header>
            <ul
                style={{
                    listStyle: 'none',
                    padding: 0,
                    margin: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                }}
            >
                {gaps.map((gap) => {
                    const isOpen = expandedGapId === gap.id
                    return (
                        <li key={gap.id}>
                            <GapRow
                                gap={gap}
                                isOpen={isOpen}
                                onToggle={() => setExpandedGapId(isOpen ? null : gap.id)}
                            />
                        </li>
                    )
                })}
            </ul>
        </section>
    )
}

function GapRow({ gap, isOpen, onToggle }: { gap: Gap; isOpen: boolean; onToggle: () => void }) {
    const detailId = `whats-missing-detail-${gap.id}`
    return (
        <div
            style={{
                background: 'var(--bg-surface-2)',
                borderRadius: '6px',
                borderLeft: '3px solid var(--accent-blue)',
                overflow: 'hidden',
            }}
        >
            <button
                type="button"
                onClick={onToggle}
                aria-expanded={isOpen}
                aria-controls={detailId}
                style={{
                    width: '100%',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '10px 14px',
                    textAlign: 'left',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    color: 'var(--text-primary)',
                }}
            >
                <span
                    style={{
                        fontFamily: 'var(--font-mono, monospace)',
                        fontSize: '0.7rem',
                        fontWeight: 600,
                        color: 'var(--text-tertiary)',
                        flexShrink: 0,
                    }}
                >
                    {gap.id}
                </span>
                <h4
                    style={{
                        fontSize: '0.9rem',
                        fontWeight: 700,
                        margin: 0,
                        flex: 1,
                    }}
                >
                    {gap.title}
                </h4>
                <span
                    aria-hidden="true"
                    style={{
                        fontSize: '0.75rem',
                        color: 'var(--text-tertiary)',
                        transform: isOpen ? 'rotate(180deg)' : 'none',
                        transition: 'transform 0.15s ease',
                    }}
                >
                    ▾
                </span>
            </button>
            {isOpen ? (
                <div
                    id={detailId}
                    style={{
                        padding: '0 14px 12px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '6px',
                    }}
                >
                    <p
                        style={{
                            fontSize: '0.85rem',
                            lineHeight: 1.7,
                            color: 'var(--text-secondary)',
                            margin: 0,
                        }}
                    >
                        {gap.description}
                    </p>
                    <p
                        style={{
                            fontSize: '0.85rem',
                            lineHeight: 1.7,
                            color: 'var(--accent-blue)',
                            margin: 0,
                            fontStyle: 'italic',
                        }}
                    >
                        {gap.deepDiveFraming}
                    </p>
                </div>
            ) : null}
        </div>
    )
}
