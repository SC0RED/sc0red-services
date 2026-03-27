import { COMPARISON_COLORS } from '@/components/comparison/constants'
import { RISK_CATEGORIES, TIER_COLORS, getRiskTier } from '@/lib/utils/riskUtils'
import { CAT_LABELS } from '@/components/RiskBreakdown'
import type { AnalysisData } from '@/lib/types/api'

interface ComparisonRiskTableProps {
    analyses: AnalysisData[]
}

export default function ComparisonRiskTable({ analyses }: ComparisonRiskTableProps) {
    return (
        <div className="card" style={{ overflowX: 'auto', marginBottom: '1.5rem' }}>
            <div style={{ fontWeight: 600, padding: '1.25rem 1.25rem 0.75rem', fontSize: '0.9375rem' }}>
                Risk Dimension Breakdown
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <th
                            style={{
                                padding: '0.75rem 1.25rem',
                                textAlign: 'left',
                                fontSize: '0.8125rem',
                                fontWeight: 600,
                                color: 'var(--text-secondary)',
                                textTransform: 'uppercase',
                                letterSpacing: '0.06em',
                            }}
                        >
                            Risk Category
                        </th>
                        {analyses.map((analysis, index) => (
                            <th
                                key={analysis.id}
                                style={{
                                    padding: '0.75rem 1.25rem',
                                    textAlign: 'center',
                                    fontSize: '0.8125rem',
                                    fontWeight: 600,
                                    color: COMPARISON_COLORS[index],
                                }}
                            >
                                {analysis.companyName}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {RISK_CATEGORIES.map((cat, rowIndex) => {
                        const scores = analyses.map((a) => {
                            const riskScore = a.riskScores?.find((r) => r.category === cat.id)
                            return riskScore?.score ?? 0
                        })
                        const maxScore = Math.max(...scores)

                        return (
                            <tr
                                key={cat.id}
                                style={{
                                    borderBottom:
                                        rowIndex < RISK_CATEGORIES.length - 1
                                            ? '1px solid var(--border-subtle)'
                                            : 'none',
                                }}
                            >
                                <td
                                    style={{
                                        padding: '0.875rem 1.25rem',
                                        fontSize: '0.875rem',
                                        fontWeight: 500,
                                    }}
                                >
                                    {CAT_LABELS[cat.id] ?? cat.name}
                                </td>
                                {scores.map((score, colIndex) => {
                                    const tier = getRiskTier(score)
                                    const isHighest = score === maxScore && maxScore > 0
                                    return (
                                        <td
                                            key={analyses[colIndex].id}
                                            style={{
                                                padding: '0.875rem 1.25rem',
                                                textAlign: 'center',
                                            }}
                                        >
                                            <div
                                                style={{
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    justifyContent: 'center',
                                                    gap: '0.5rem',
                                                }}
                                            >
                                                <span
                                                    style={{
                                                        fontWeight: isHighest ? 700 : 500,
                                                        fontSize: '1rem',
                                                        color: TIER_COLORS[tier],
                                                        minWidth: '2rem',
                                                    }}
                                                >
                                                    {score.toFixed(1)}
                                                </span>
                                                <div
                                                    style={{
                                                        width: '60px',
                                                        height: '6px',
                                                        borderRadius: '3px',
                                                        background: 'var(--bg-surface-3)',
                                                        overflow: 'hidden',
                                                    }}
                                                >
                                                    <div
                                                        style={{
                                                            width: `${(score / 10) * 100}%`,
                                                            height: '100%',
                                                            borderRadius: '3px',
                                                            background: TIER_COLORS[tier],
                                                        }}
                                                    />
                                                </div>
                                            </div>
                                        </td>
                                    )
                                })}
                            </tr>
                        )
                    })}
                </tbody>
            </table>
        </div>
    )
}
