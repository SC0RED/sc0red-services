'use client'

import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer } from 'recharts'

import RiskBadge from '@/components/RiskBadge'
import { CAT_LABELS, RISK_CATEGORIES, TIER_COLORS, getRiskTier } from '@/lib/utils/riskUtils'
import type { AnalysisData } from '@/lib/types/api'

interface AnalysisOverviewCardsProps {
    data: AnalysisData
}

/**
 * Score card + risk-dimensions radar chart row at the top of the
 * analysis detail page. Extracted from `AnalysisDetail` to keep the
 * parent under the 360-line frontend file budget; pure presentation,
 * no state, no side effects.
 */
export default function AnalysisOverviewCards({ data }: AnalysisOverviewCardsProps) {
    const tier = data.riskTier || getRiskTier(data.overallRiskScore ?? 0)
    const tierColor = TIER_COLORS[tier] || 'var(--text-secondary)'

    const riskScores = data.riskScores ?? []
    const radarData = RISK_CATEGORIES.map((cat) => {
        const rs = riskScores.find((r) => r.category === cat.id)
        return { category: CAT_LABELS[cat.id] ?? cat.name, score: rs?.score ?? 0, fullMark: 10 }
    })

    return (
        <div
            style={{
                display: 'grid',
                gridTemplateColumns: '280px 1fr',
                gap: '1.25rem',
                marginBottom: '1.5rem',
            }}
        >
            <div
                className="card card--metric"
                style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                }}
            >
                <div
                    style={{
                        fontSize: '0.875rem',
                        color: 'var(--text-secondary)',
                        fontWeight: 500,
                        marginBottom: '0.75rem',
                        textTransform: 'uppercase',
                        letterSpacing: '0.08em',
                    }}
                >
                    Overall AI Risk Score
                </div>
                <div
                    style={{
                        width: '120px',
                        height: '120px',
                        borderRadius: '50%',
                        border: `6px solid ${tierColor}`,
                        boxShadow: `0 0 40px ${tierColor}40`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        marginBottom: '1.25rem',
                    }}
                >
                    <span
                        style={{
                            fontSize: '2.5rem',
                            fontWeight: 800,
                            color: tierColor,
                            lineHeight: 1,
                        }}
                    >
                        {data.overallRiskScore?.toFixed(1) || '—'}
                    </span>
                </div>
                <RiskBadge tier={tier} />
                {data.analysisSummary && (
                    <p
                        style={{
                            marginTop: '1rem',
                            fontSize: '0.875rem',
                            color: 'var(--text-secondary)',
                            lineHeight: 1.6,
                            textAlign: 'left',
                        }}
                    >
                        {data.analysisSummary}
                    </p>
                )}
            </div>

            <div className="card card--rich">
                <div style={{ fontWeight: 600, marginBottom: '1rem', fontSize: '1rem' }}>Risk Dimensions</div>
                <ResponsiveContainer width="100%" height={280}>
                    <RadarChart data={radarData}>
                        <PolarGrid stroke="var(--border)" />
                        <PolarAngleAxis
                            dataKey="category"
                            tick={{ fill: 'var(--text-primary)', fontSize: 11, fontWeight: 500 }}
                        />
                        <Radar
                            name="Risk"
                            dataKey="score"
                            stroke={tierColor}
                            fill={tierColor}
                            fillOpacity={0.12}
                            strokeWidth={2}
                        />
                    </RadarChart>
                </ResponsiveContainer>
            </div>
        </div>
    )
}
