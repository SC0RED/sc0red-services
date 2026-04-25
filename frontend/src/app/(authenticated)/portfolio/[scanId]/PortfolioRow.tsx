import Link from 'next/link'
import { getRiskTierLabel, TIER_COLORS } from '@/lib/utils/riskUtils'
import type { ScanAnalysis } from '@/lib/types/api'

/**
 * One row in the bottom "All Companies" table. Mirrors the state-driven
 * treatment of the heatmap card — pending rows show a quiet "Pending"
 * affordance, scanning rows show the pipeline label, done rows show the
 * score, failed rows show "Failed".
 */
export default function PortfolioRow({
    analysis,
    isLast,
}: {
    analysis: ScanAnalysis
    isLast: boolean
}): JSX.Element {
    const tier = analysis.riskTier
    return (
        <tr
            data-state={analysis.state}
            style={{
                borderBottom: isLast ? 'none' : '1px solid var(--border-subtle)',
            }}
        >
            <td style={{ padding: '1rem 1.25rem' }}>
                <div style={{ fontWeight: 500 }}>{analysis.companyName || '—'}</div>
                {analysis.companyUrl && (
                    <div
                        style={{
                            fontSize: '0.8125rem',
                            color: 'var(--text-tertiary)',
                        }}
                    >
                        {analysis.companyUrl}
                    </div>
                )}
            </td>
            <td
                style={{
                    padding: '1rem 1.25rem',
                    color: 'var(--text-secondary)',
                    fontSize: '0.875rem',
                }}
            >
                {analysis.industry || '—'}
            </td>
            <td style={{ padding: '1rem 1.25rem' }}>
                <RowStatusCell analysis={analysis} />
            </td>
            <td style={{ padding: '1rem 1.25rem' }}>
                {tier && <span className={`badge badge-${tier}`}>{getRiskTierLabel(tier)}</span>}
            </td>
            <td style={{ padding: '1rem 1.25rem' }}>
                {analysis.state === 'done' && (
                    <Link href={`/analysis/${analysis.id}`} className="btn btn-ghost btn-sm">
                        View Report
                    </Link>
                )}
            </td>
        </tr>
    )
}

function RowStatusCell({ analysis }: { analysis: ScanAnalysis }): JSX.Element {
    const tier = analysis.riskTier
    if (analysis.state === 'done') {
        // Same fail-soft treatment as PortfolioCard: a done row whose
        // record never got an `overall_risk_score` persisted shows a
        // neutral "Analyzed" instead of falling through to "Pending".
        if (analysis.overallRiskScore === null) {
            return <span style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>Analyzed</span>
        }
        return (
            <span
                style={{
                    fontWeight: 700,
                    fontSize: '1.1rem',
                    color: tier ? TIER_COLORS[tier] : 'var(--text-secondary)',
                }}
            >
                {Number(analysis.overallRiskScore).toFixed(1)}
            </span>
        )
    }
    if (analysis.state === 'failed') {
        return (
            <span style={{ color: 'var(--risk-critical)', fontSize: '0.8125rem', fontWeight: 600 }}>
                Failed
            </span>
        )
    }
    if (analysis.state === 'scanning') {
        return (
            <span style={{ color: 'var(--accent-blue)', fontSize: '0.8125rem' }}>
                {analysis.pipelineLabel || 'Analyzing…'}
            </span>
        )
    }
    return <span style={{ color: 'var(--text-tertiary)' }}>Pending</span>
}
