import Link from 'next/link'
import { getRiskTierLabel, TIER_COLORS } from '@/lib/utils/riskUtils'
import type { ScanAnalysis } from '@/lib/types/api'

/**
 * One card in the heatmap grid. Visual treatment is selected directly
 * from `analysis.state` — never inferred from null-checks on score /
 * analyzedAt / pipelineProgress. The `data-state` attribute is exposed
 * so vitest tests (and visual-regression tooling) can assert by state.
 *
 * Pending and scanning cards link to `#` (no analysis page yet); only
 * `done` cards have an `/analysis/{id}` destination. Failed cards are
 * also non-navigable — there's no successful report to show.
 */
export default function PortfolioCard({ analysis }: { analysis: ScanAnalysis }): JSX.Element {
    const tier = analysis.riskTier
    const tierColor = tier ? TIER_COLORS[tier] : 'var(--text-tertiary)'
    const isTerminal = analysis.state === 'done' || analysis.state === 'failed'
    const fallbackName = analysis.state === 'failed' ? 'Unknown Company' : ''
    const href = analysis.state === 'done' ? `/analysis/${analysis.id}` : '#'

    return (
        <Link key={analysis.id} href={href} style={{ textDecoration: 'none' }}>
            <div
                className="card"
                data-state={analysis.state}
                style={{
                    padding: '1.125rem',
                    borderTop: tier ? `3px solid ${tierColor}` : '3px solid var(--border-subtle)',
                    opacity: isTerminal ? 1 : 0.7,
                }}
            >
                <div
                    className="truncate"
                    style={{
                        fontWeight: 600,
                        fontSize: '0.9rem',
                        marginBottom: '0.375rem',
                    }}
                >
                    {analysis.companyName || fallbackName}
                </div>
                {analysis.industry && (
                    <div
                        className="truncate"
                        style={{
                            fontSize: '0.75rem',
                            color: 'var(--text-tertiary)',
                            marginBottom: '0.625rem',
                        }}
                    >
                        {analysis.industry}
                    </div>
                )}
                <CardStateContent analysis={analysis} />
            </div>
        </Link>
    )
}

function CardStateContent({ analysis }: { analysis: ScanAnalysis }): JSX.Element {
    const tier = analysis.riskTier
    const tierColor = tier ? TIER_COLORS[tier] : 'var(--text-tertiary)'

    if (analysis.state === 'done') {
        // A done card without a numeric score means the record was marked
        // analyzed but the score never got persisted (rare backend
        // inconsistency). Surface a neutral "Analyzed" affordance so the
        // wrapper's `data-state="done"` and the inner content stay
        // consistent — no Pending text leaking onto a done card.
        if (analysis.overallRiskScore === null) {
            return (
                <span
                    style={{
                        fontSize: '0.75rem',
                        color: 'var(--text-secondary)',
                        fontStyle: 'italic',
                    }}
                >
                    Analyzed
                </span>
            )
        }
        return (
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                }}
            >
                <span style={{ fontSize: '1.5rem', fontWeight: 800, color: tierColor }}>
                    {Number(analysis.overallRiskScore).toFixed(1)}
                </span>
                {tier && (
                    <span className={`badge badge-${tier}`} style={{ fontSize: '0.7rem' }}>
                        {getRiskTierLabel(tier)}
                    </span>
                )}
            </div>
        )
    }

    if (analysis.state === 'failed') {
        return (
            <span
                style={{
                    display: 'inline-block',
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    padding: '0.2rem 0.5rem',
                    borderRadius: '4px',
                    backgroundColor: 'rgba(239, 68, 68, 0.15)',
                    color: 'var(--risk-critical)',
                }}
            >
                FAILED
            </span>
        )
    }

    if (analysis.state === 'scanning') {
        const label = analysis.pipelineLabel || 'Analyzing...'
        return (
            <div
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                aria-live="polite"
                aria-label={`Scanning: ${label}`}
            >
                <span className="pulse-dot" aria-hidden="true" />
                <span className="truncate" style={{ fontSize: '0.75rem', color: 'var(--accent-blue)' }}>
                    {label}
                </span>
            </div>
        )
    }

    // pending — and any unexpected state — fall through to the quiet treatment
    return (
        <span
            style={{
                fontSize: '0.75rem',
                color: 'var(--text-tertiary)',
                opacity: 0.6,
            }}
        >
            Pending
        </span>
    )
}
