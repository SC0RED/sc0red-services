import { getRiskTier, RISK_CATEGORIES, TIER_COLORS } from '@/lib/utils/riskUtils'
import type { RiskScore } from '@/lib/types/api'

interface PrintRiskTableProps {
    riskScores: RiskScore[]
}

/**
 * Risk Profile section — every category as a fixed-expanded row,
 * sorted by score descending. No collapse controls, no chevrons:
 * the rationale text is always visible.
 *
 * Print-only counterpart to `RiskBreakdown`. The screen component is
 * collapsed-by-default with a chevron toggle, which is exactly what
 * the print PDF must NOT do — the rationale is the most useful field
 * for a PE reader and was previously hidden behind interaction.
 *
 * Rows missing a `rationale` render the score bar only. No empty
 * paragraph placeholder.
 */
export default function PrintRiskTable({ riskScores }: PrintRiskTableProps) {
    if (!riskScores.length) return null

    const sorted = [...riskScores].sort((a, b) => b.score - a.score)

    return (
        <section className="print-section print-section--break-before">
            <h2>Risk Profile</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {sorted.map((rs) => {
                    const tier = getRiskTier(rs.score)
                    const color = TIER_COLORS[tier] ?? 'var(--text-secondary)'
                    const label = RISK_CATEGORIES.find((c) => c.id === rs.category)?.name ?? rs.category
                    return (
                        <div
                            key={rs.category}
                            className="print-risk-row"
                            style={{
                                padding: '14px 16px',
                                background: 'var(--bg-surface-2)',
                                borderRadius: '8px',
                                border: '1px solid var(--border-subtle)',
                            }}
                        >
                            <div
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '14px',
                                    marginBottom: rs.rationale ? '10px' : 0,
                                }}
                            >
                                <div
                                    style={{
                                        width: '40px',
                                        height: '40px',
                                        borderRadius: '8px',
                                        background: `${color}20`,
                                        border: `1px solid ${color}40`,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        flexShrink: 0,
                                    }}
                                >
                                    <span
                                        style={{
                                            fontSize: '1.05rem',
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
                                            fontSize: '0.95rem',
                                            marginBottom: '6px',
                                        }}
                                    >
                                        {label}
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
                                            }}
                                        />
                                    </div>
                                </div>
                                <span
                                    style={{
                                        fontSize: '0.75rem',
                                        fontWeight: 600,
                                        color,
                                        textTransform: 'uppercase',
                                        letterSpacing: '0.04em',
                                        flexShrink: 0,
                                    }}
                                >
                                    {tier}
                                </span>
                            </div>
                            {rs.rationale ? (
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
                            ) : null}
                        </div>
                    )
                })}
            </div>
        </section>
    )
}
