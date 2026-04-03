import RiskBadge from '@/components/RiskBadge'
import { getRiskTier, TIER_COLORS } from '@/lib/utils/riskUtils'
import type { AnalysisData } from '@/lib/types/api'

import { COMPARISON_COLORS } from '@/components/comparison/constants'

interface ComparisonScoreCardsProps {
    analyses: AnalysisData[]
}

export default function ComparisonScoreCards({ analyses }: ComparisonScoreCardsProps) {
    return (
        <div
            style={{
                display: 'grid',
                gridTemplateColumns: `repeat(${analyses.length}, 1fr)`,
                gap: '1.25rem',
                marginBottom: '1.5rem',
            }}
        >
            {analyses.map((analysis, index) => {
                const tier = analysis.riskTier || getRiskTier(analysis.overallRiskScore ?? 0)
                const tierColor = TIER_COLORS[tier] || 'var(--text-secondary)'
                const comparisonColor = COMPARISON_COLORS[index]

                return (
                    <div
                        key={analysis.id}
                        className="card"
                        style={{
                            padding: '1.5rem',
                            textAlign: 'center',
                            borderTop: `3px solid ${comparisonColor}`,
                        }}
                    >
                        <div
                            style={{
                                fontSize: '0.75rem',
                                color: comparisonColor,
                                fontWeight: 600,
                                textTransform: 'uppercase',
                                letterSpacing: '0.08em',
                                marginBottom: '0.75rem',
                            }}
                        >
                            Company {index + 1}
                        </div>
                        <div style={{ fontWeight: 700, fontSize: '1.125rem', marginBottom: '0.25rem' }}>
                            {analysis.companyName}
                        </div>
                        {analysis.industry && (
                            <div
                                style={{
                                    fontSize: '0.8125rem',
                                    color: 'var(--text-tertiary)',
                                    marginBottom: '1rem',
                                }}
                            >
                                {analysis.industry}
                            </div>
                        )}
                        <div
                            style={{
                                width: '90px',
                                height: '90px',
                                borderRadius: '50%',
                                border: `5px solid ${tierColor}`,
                                boxShadow: `0 0 30px ${tierColor}40`,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                margin: '0 auto 1rem',
                            }}
                        >
                            <span
                                style={{ fontSize: '2rem', fontWeight: 800, color: tierColor, lineHeight: 1 }}
                            >
                                {analysis.overallRiskScore?.toFixed(1) || '—'}
                            </span>
                        </div>
                        <RiskBadge tier={tier} />
                    </div>
                )
            })}
        </div>
    )
}
