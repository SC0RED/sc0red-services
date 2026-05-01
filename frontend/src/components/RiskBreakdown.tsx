'use client'

import { useState } from 'react'

import RiskBadge from '@/components/RiskBadge'
import { getRiskTier, RISK_CATEGORIES, TIER_COLORS } from '@/lib/utils/riskUtils'
import type { RiskScore } from '@/lib/types/api'

interface RiskBreakdownProps {
    riskScores: RiskScore[]
}

export default function RiskBreakdown({ riskScores }: RiskBreakdownProps) {
    const [expandedRisk, setExpandedRisk] = useState<string | null>(null)

    return (
        <div style={{ marginBottom: '2rem' }}>
            <h2 className="section-header">Risk Breakdown</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
                {[...riskScores]
                    .sort((a: RiskScore, b: RiskScore) => b.score - a.score)
                    .map((rs) => {
                        const rsTier = getRiskTier(rs.score)
                        const color = TIER_COLORS[rsTier]
                        const catName = RISK_CATEGORIES.find((c) => c.id === rs.category)?.name ?? rs.category
                        const isOpen = expandedRisk === rs.category
                        return (
                            <div key={rs.category} className="card" style={{ overflow: 'hidden' }}>
                                <button
                                    onClick={() => setExpandedRisk(isOpen ? null : rs.category)}
                                    aria-expanded={isOpen}
                                    aria-controls={`risk-detail-${rs.category}`}
                                    style={{
                                        width: '100%',
                                        background: 'none',
                                        border: 'none',
                                        cursor: 'pointer',
                                        padding: '1rem 1.25rem',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '1rem',
                                        textAlign: 'left',
                                    }}
                                >
                                    <div
                                        style={{
                                            width: '44px',
                                            height: '44px',
                                            borderRadius: 'var(--radius-md)',
                                            background: `${color}18`,
                                            border: `1px solid ${color}30`,
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            flexShrink: 0,
                                        }}
                                    >
                                        <span
                                            style={{
                                                fontSize: '1.125rem',
                                                fontWeight: 800,
                                                color,
                                            }}
                                        >
                                            {rs.score}
                                        </span>
                                    </div>
                                    <div style={{ flex: 1 }}>
                                        <div
                                            style={{
                                                fontWeight: 600,
                                                fontSize: '0.9375rem',
                                                marginBottom: '2px',
                                            }}
                                        >
                                            {catName}
                                        </div>
                                        <div
                                            style={{
                                                width: '100%',
                                                height: '4px',
                                                background: 'var(--bg-surface-3)',
                                                borderRadius: '2px',
                                                overflow: 'hidden',
                                            }}
                                        >
                                            <div
                                                style={{
                                                    height: '100%',
                                                    width: `${(rs.score / 10) * 100}%`,
                                                    background: color,
                                                    borderRadius: '2px',
                                                    transition: 'width 0.6s ease',
                                                }}
                                            />
                                        </div>
                                    </div>
                                    <div
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '0.75rem',
                                            flexShrink: 0,
                                        }}
                                    >
                                        <RiskBadge tier={rsTier} />
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
                                            }}
                                        >
                                            <polyline points="6 9 12 15 18 9" />
                                        </svg>
                                    </div>
                                </button>
                                {isOpen && (
                                    <div
                                        id={`risk-detail-${rs.category}`}
                                        style={{
                                            padding: '0 1.25rem 1.25rem',
                                            display: 'flex',
                                            flexDirection: 'column',
                                            gap: '0.75rem',
                                        }}
                                    >
                                        <div className="divider" />
                                        {rs.rationale && (
                                            <p
                                                style={{
                                                    fontSize: '0.875rem',
                                                    lineHeight: 1.7,
                                                    color: 'var(--text-primary)',
                                                }}
                                            >
                                                {rs.rationale}
                                            </p>
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
