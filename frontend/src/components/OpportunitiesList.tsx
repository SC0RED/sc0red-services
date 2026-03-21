'use client'

import { useState } from 'react'

import { LEVER_COLORS } from '@/lib/utils/leverColors'
import type { Opportunity } from '@/lib/types/api'

function ImpactBadge({ impact }: { impact: string }) {
    const colorMap: Record<string, string> = { High: 'low', Medium: 'moderate', Low: 'neutral' }
    return <span className={`badge badge-${colorMap[impact] || 'neutral'}`}>{impact} Impact</span>
}

function TimelineBadge({ timeline }: { timeline: string }) {
    return (
        <span className="badge badge-blue" style={{ fontSize: '0.7rem' }}>
            {timeline}
        </span>
    )
}

interface OpportunitiesListProps {
    opportunities: Opportunity[]
    activeLever: string
}

export default function OpportunitiesList({ opportunities, activeLever }: OpportunitiesListProps) {
    const [activeOppCat, setActiveOppCat] = useState<string>('All')
    const [expandedOpp, setExpandedOpp] = useState<string | null>(null)

    const uniqueCategories = opportunities
        .map((o) => o.strategic_category)
        .filter((cat, index, arr) => arr.indexOf(cat) === index)
    const oppCategories = ['All', ...uniqueCategories]
    const filteredOpps = opportunities.filter((o) => {
        if (activeOppCat !== 'All' && o.strategic_category !== activeOppCat) return false
        if (activeLever !== 'All' && o.value_lever !== activeLever) return false
        return true
    })

    return (
        <div style={{ marginBottom: '2rem' }}>
            <div
                style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '1rem',
                    flexWrap: 'wrap',
                    gap: '0.75rem',
                }}
            >
                <h2 style={{ fontSize: '1.125rem', fontWeight: 700 }}>
                    AI Opportunities ({opportunities.length})
                </h2>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    {oppCategories.map((cat) => (
                        <button
                            key={cat}
                            onClick={() => setActiveOppCat(cat)}
                            style={{
                                padding: '0.3rem 0.75rem',
                                borderRadius: 'var(--radius-full)',
                                border: '1px solid',
                                borderColor: activeOppCat === cat ? 'var(--accent-blue)' : 'var(--border)',
                                background: activeOppCat === cat ? 'rgba(59,123,246,0.1)' : 'transparent',
                                color: activeOppCat === cat ? 'var(--accent-blue)' : 'var(--text-secondary)',
                                fontSize: '0.8rem',
                                fontWeight: 500,
                                cursor: 'pointer',
                                transition: 'all var(--transition-fast)',
                            }}
                        >
                            {cat}
                        </button>
                    ))}
                </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
                {filteredOpps.map((opp: Opportunity, i: number) => {
                    const isOpen = expandedOpp === `${i}`
                    return (
                        <div key={i} className="card" style={{ overflow: 'hidden' }}>
                            <button
                                onClick={() => setExpandedOpp(isOpen ? null : `${i}`)}
                                style={{
                                    width: '100%',
                                    background: 'none',
                                    border: 'none',
                                    cursor: 'pointer',
                                    padding: '1.25rem',
                                    textAlign: 'left',
                                }}
                            >
                                <div
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'flex-start',
                                        gap: '1rem',
                                    }}
                                >
                                    <div style={{ flex: 1 }}>
                                        <div
                                            style={{
                                                fontWeight: 700,
                                                fontSize: '0.9875rem',
                                                marginBottom: '0.5rem',
                                            }}
                                        >
                                            {opp.title}
                                        </div>
                                        <div
                                            style={{
                                                display: 'flex',
                                                gap: '0.5rem',
                                                flexWrap: 'wrap',
                                            }}
                                        >
                                            <ImpactBadge impact={opp.impact_rating} />
                                            <TimelineBadge timeline={opp.timeline} />
                                            <span className="badge badge-neutral">
                                                {opp.strategic_category}
                                            </span>
                                            {opp.value_lever && (
                                                <span
                                                    style={{
                                                        padding: '0.15rem 0.5rem',
                                                        borderRadius: 'var(--radius-full)',
                                                        fontSize: '0.7rem',
                                                        fontWeight: 500,
                                                        border: '1px solid',
                                                        borderColor:
                                                            LEVER_COLORS[opp.value_lever] ||
                                                            'var(--text-secondary)',
                                                        color:
                                                            LEVER_COLORS[opp.value_lever] ||
                                                            'var(--text-secondary)',
                                                    }}
                                                >
                                                    {opp.value_lever}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <svg
                                        width="16"
                                        height="16"
                                        viewBox="0 0 24 24"
                                        fill="none"
                                        stroke="var(--text-tertiary)"
                                        strokeWidth="2"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        style={{
                                            transform: isOpen ? 'rotate(180deg)' : 'none',
                                            transition: 'transform 0.2s',
                                            flexShrink: 0,
                                            marginTop: '4px',
                                        }}
                                    >
                                        <polyline points="6 9 12 15 18 9" />
                                    </svg>
                                </div>
                            </button>

                            {isOpen && (
                                <div style={{ padding: '0 1.25rem 1.5rem' }}>
                                    <div className="divider" style={{ marginBottom: '1.25rem' }} />

                                    <p
                                        style={{
                                            fontSize: '0.9rem',
                                            lineHeight: 1.75,
                                            color: 'var(--text-primary)',
                                            marginBottom: '1.5rem',
                                            whiteSpace: 'pre-line',
                                        }}
                                    >
                                        {opp.description}
                                    </p>

                                    {opp.implementation_steps && opp.implementation_steps.length > 0 && (
                                        <div style={{ marginBottom: '1.25rem' }}>
                                            <div
                                                style={{
                                                    fontWeight: 600,
                                                    fontSize: '0.875rem',
                                                    color: 'var(--text-secondary)',
                                                    marginBottom: '0.75rem',
                                                    textTransform: 'uppercase',
                                                    letterSpacing: '0.06em',
                                                }}
                                            >
                                                Implementation Steps
                                            </div>
                                            <div
                                                style={{
                                                    display: 'flex',
                                                    flexDirection: 'column',
                                                    gap: '0.5rem',
                                                }}
                                            >
                                                {opp.implementation_steps.map((step, si) => (
                                                    <div
                                                        key={si}
                                                        style={{
                                                            display: 'flex',
                                                            gap: '0.75rem',
                                                            alignItems: 'flex-start',
                                                        }}
                                                    >
                                                        <span
                                                            style={{
                                                                minWidth: '22px',
                                                                height: '22px',
                                                                borderRadius: '50%',
                                                                background: 'rgba(59,123,246,0.12)',
                                                                color: 'var(--accent-blue)',
                                                                display: 'flex',
                                                                alignItems: 'center',
                                                                justifyContent: 'center',
                                                                fontSize: '0.75rem',
                                                                fontWeight: 700,
                                                                flexShrink: 0,
                                                                marginTop: '2px',
                                                            }}
                                                        >
                                                            {si + 1}
                                                        </span>
                                                        <p
                                                            style={{
                                                                fontSize: '0.875rem',
                                                                lineHeight: 1.6,
                                                            }}
                                                        >
                                                            {step}
                                                        </p>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    <div
                                        style={{
                                            display: 'grid',
                                            gridTemplateColumns: '1fr 1fr',
                                            gap: '0.875rem',
                                            marginBottom: '1.25rem',
                                        }}
                                    >
                                        <div
                                            style={{
                                                padding: '1rem',
                                                background: 'var(--bg-surface-3)',
                                                borderRadius: 'var(--radius-md)',
                                                borderLeft: '3px solid var(--risk-moderate)',
                                            }}
                                        >
                                            <div
                                                style={{
                                                    fontSize: '0.75rem',
                                                    fontWeight: 600,
                                                    color: 'var(--text-tertiary)',
                                                    marginBottom: '0.375rem',
                                                    textTransform: 'uppercase',
                                                    letterSpacing: '0.06em',
                                                }}
                                            >
                                                Estimated Investment
                                            </div>
                                            <div
                                                style={{
                                                    fontWeight: 700,
                                                    color: 'var(--risk-moderate)',
                                                }}
                                            >
                                                {opp.investment_range}
                                            </div>
                                        </div>
                                        <div
                                            style={{
                                                padding: '1rem',
                                                background: 'var(--bg-surface-3)',
                                                borderRadius: 'var(--radius-md)',
                                                borderLeft: '3px solid var(--risk-low)',
                                            }}
                                        >
                                            <div
                                                style={{
                                                    fontSize: '0.75rem',
                                                    fontWeight: 600,
                                                    color: 'var(--text-tertiary)',
                                                    marginBottom: '0.375rem',
                                                    textTransform: 'uppercase',
                                                    letterSpacing: '0.06em',
                                                }}
                                            >
                                                Potential ROI
                                            </div>
                                            <div
                                                style={{
                                                    fontWeight: 600,
                                                    color: 'var(--risk-low)',
                                                    fontSize: '0.9rem',
                                                }}
                                            >
                                                {opp.roi_estimate}
                                            </div>
                                        </div>
                                    </div>

                                    {opp.related_services && opp.related_services.length > 0 && (
                                        <div>
                                            <div
                                                style={{
                                                    fontWeight: 600,
                                                    fontSize: '0.875rem',
                                                    color: 'var(--text-secondary)',
                                                    marginBottom: '0.75rem',
                                                    textTransform: 'uppercase',
                                                    letterSpacing: '0.06em',
                                                }}
                                            >
                                                Implementation Partners
                                            </div>
                                            <div
                                                style={{
                                                    display: 'flex',
                                                    gap: '0.5rem',
                                                    flexWrap: 'wrap',
                                                }}
                                            >
                                                {opp.related_services.map((svc, si) => (
                                                    <span key={si} className="badge badge-neutral">
                                                        {svc}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    )
                })}
            </div>
        </div>
    )
}
