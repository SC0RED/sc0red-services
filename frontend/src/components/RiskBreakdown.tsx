'use client'

import { useState } from 'react'

import RiskBadge from '@/components/RiskBadge'
import ExpandableCard from '@/components/ui/ExpandableCard'
import { getRiskTier, RISK_CATEGORIES, TIER_COLORS } from '@/lib/utils/riskUtils'
import type { RiskScore } from '@/lib/types/api'

interface RiskBreakdownProps {
    riskScores: RiskScore[]
}

export default function RiskBreakdown({ riskScores }: RiskBreakdownProps) {
    const [expandedRisk, setExpandedRisk] = useState<string | null>(null)

    return (
        <div style={{ marginBottom: '2rem' }}>
            {/* Section heading lives at the page level via AnalysisSection
                (analysis-detail-consistency-wrapper D3). */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
                {[...riskScores]
                    .sort((a: RiskScore, b: RiskScore) => b.score - a.score)
                    .map((rs) => {
                        const rsTier = getRiskTier(rs.score)
                        const color = TIER_COLORS[rsTier]
                        const catName = RISK_CATEGORIES.find((c) => c.id === rs.category)?.name ?? rs.category
                        const isOpen = expandedRisk === rs.category
                        return (
                            <ExpandableCard
                                key={rs.category}
                                id={rs.category}
                                isOpen={isOpen}
                                onToggle={() => setExpandedRisk(isOpen ? null : rs.category)}
                                header={
                                    <div
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '1rem',
                                            width: '100%',
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
                                        <RiskBadge tier={rsTier} />
                                    </div>
                                }
                            >
                                {rs.rationale && (
                                    <p
                                        style={{
                                            fontSize: '0.875rem',
                                            lineHeight: 1.7,
                                            color: 'var(--text-primary)',
                                            margin: 0,
                                        }}
                                    >
                                        {rs.rationale}
                                    </p>
                                )}
                            </ExpandableCard>
                        )
                    })}
            </div>
        </div>
    )
}
