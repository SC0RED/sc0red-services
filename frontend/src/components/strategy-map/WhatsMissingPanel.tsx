import type { Gap } from '@/lib/types/api'

interface WhatsMissingPanelProps {
    gaps: Gap[]
}

/**
 * "What's Missing?" panel — the conversion engine of the strategy
 * map.
 *
 * Per Kaplan & Norton's Mobil case study (HBR 2000): strategy maps
 * EXPOSE strategic gaps. Each generated map identifies 2-4 gaps
 * suitable for a deep-dive conversation. Each gap has its own
 * `deepDiveFraming` sentence describing what a Vector Advisory
 * engagement would specifically address.
 *
 * Renders as a labeled section beneath the strategy map, immediately
 * above the deep-dive CTA. The panel makes the CTA *specific*:
 * generic "contact us" → low conversion. "Contact us to discuss
 * your customer-segment strategy" → higher conversion.
 */
export default function WhatsMissingPanel({ gaps }: WhatsMissingPanelProps) {
    if (gaps.length === 0) return null

    return (
        <section
            data-testid="strategy-map-whats-missing"
            style={{
                marginTop: '24px',
                padding: '18px 20px',
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
                    marginBottom: '12px',
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
                    gap: '12px',
                }}
            >
                {gaps.map((gap) => (
                    <li
                        key={gap.id}
                        style={{
                            padding: '12px 14px',
                            background: 'var(--bg-surface-2)',
                            borderRadius: '6px',
                            borderLeft: '3px solid var(--accent-blue)',
                        }}
                    >
                        <div
                            style={{
                                display: 'flex',
                                alignItems: 'baseline',
                                gap: '8px',
                                marginBottom: '6px',
                            }}
                        >
                            <span
                                style={{
                                    fontFamily: 'var(--font-mono, monospace)',
                                    fontSize: '0.7rem',
                                    fontWeight: 600,
                                    color: 'var(--text-tertiary)',
                                }}
                            >
                                {gap.id}
                            </span>
                            <h4
                                style={{
                                    fontSize: '0.9rem',
                                    fontWeight: 700,
                                    margin: 0,
                                    color: 'var(--text-primary)',
                                }}
                            >
                                {gap.title}
                            </h4>
                        </div>
                        <p
                            style={{
                                fontSize: '0.85rem',
                                lineHeight: 1.7,
                                color: 'var(--text-secondary)',
                                margin: '0 0 6px',
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
                    </li>
                ))}
            </ul>
        </section>
    )
}
