import Link from 'next/link'

import DeleteAnalysisButton from '@/components/DeleteAnalysisButton'
import { getRiskTierLabel, TIER_COLORS } from '@/lib/utils/riskUtils'
import type { AnalysisItem } from '@/lib/types/api'

interface AnalysisRowProps {
    analysis: AnalysisItem
    selected: boolean
    selectionDisabled: boolean
    onToggleSelection: () => void
    showBorder: boolean
}

export default function AnalysisRow({
    analysis,
    selected,
    selectionDisabled,
    onToggleSelection,
    showBorder,
}: AnalysisRowProps) {
    const tier = analysis.riskTier ?? ''

    return (
        <tr style={{ borderBottom: showBorder ? '1px solid var(--border-subtle)' : 'none' }}>
            <td style={{ padding: '1rem 0.5rem', width: '40px' }}>
                <input
                    type="checkbox"
                    checked={selected}
                    onChange={onToggleSelection}
                    disabled={selectionDisabled}
                    aria-label={`Select ${analysis.companyName}`}
                    style={{
                        width: '16px',
                        height: '16px',
                        accentColor: 'var(--accent-blue)',
                        cursor: selectionDisabled ? 'not-allowed' : 'pointer',
                    }}
                />
            </td>
            <td style={{ padding: '1rem 0.75rem' }}>
                <div style={{ fontWeight: 500 }}>{analysis.companyName}</div>
                {analysis.companyUrl && (
                    <div
                        className="truncate"
                        style={{
                            fontSize: '0.8125rem',
                            color: 'var(--text-tertiary)',
                            maxWidth: '180px',
                        }}
                    >
                        {analysis.companyUrl}
                    </div>
                )}
            </td>
            <td style={{ padding: '1rem 0.75rem', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                {analysis.industry || '—'}
            </td>
            <td style={{ padding: '1rem 0.75rem' }}>
                <span
                    className={`badge badge-${analysis.scanType === 'portfolio' ? 'blue' : 'cyan'}`}
                    style={{ fontSize: '0.7rem' }}
                >
                    {analysis.scanType === 'portfolio' ? 'Portfolio' : 'Standalone'}
                </span>
            </td>
            <td style={{ padding: '1rem 0.75rem' }}>
                <span style={{ fontWeight: 700, fontSize: '1.1rem', color: TIER_COLORS[tier] }}>
                    {analysis.overallRiskScore?.toFixed(1)}
                </span>
            </td>
            <td style={{ padding: '1rem 0.75rem' }}>
                {tier && <span className={`badge badge-${tier}`}>{getRiskTierLabel(tier)}</span>}
            </td>
            <td
                style={{
                    padding: '1rem 0.75rem',
                    color: 'var(--text-tertiary)',
                    fontSize: '0.8125rem',
                    whiteSpace: 'nowrap',
                }}
            >
                {analysis.analyzedAt ? new Date(analysis.analyzedAt).toLocaleDateString() : '—'}
            </td>
            <td style={{ padding: '1rem 0.5rem', whiteSpace: 'nowrap' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.125rem' }}>
                    <Link
                        href={`/analysis/${analysis.id}`}
                        className="btn btn-ghost btn-sm"
                        title="View analysis"
                        style={{ padding: '0.25rem 0.5rem' }}
                    >
                        <svg
                            width="15"
                            height="15"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        >
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                            <circle cx="12" cy="12" r="3" />
                        </svg>
                    </Link>
                    <DeleteAnalysisButton analysisId={analysis.id} companyName={analysis.companyName} />
                </div>
            </td>
        </tr>
    )
}
