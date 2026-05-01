import type { DerivedSummary } from '@/lib/pdf/derivedSummary'
import { getRiskTier, TIER_COLORS } from '@/lib/utils/riskUtils'

interface PrintExecutiveSummaryProps {
    /** Derived view-model from `deriveSummary`. Component renders nothing
     * when this is `null`. */
    summary: DerivedSummary | null
}

/**
 * Executive Summary page — the deal-partner skim view. One page,
 * three blocks: EBITDA-uplift bar (when populated), top-3 opportunity
 * one-liners (when present), top-3 risk drivers (when present).
 *
 * Each block silently drops out when its source data is empty so a
 * partial analysis still renders a clean page rather than blank
 * sub-sections.
 *
 * Returns `null` when the upstream `deriveSummary` returned `null` —
 * i.e. the analysis has neither risks nor opportunities. The parent
 * `PrintReport` skips rendering this section entirely in that case
 * (no break-before applied), so no blank page is produced.
 */
export default function PrintExecutiveSummary({ summary }: PrintExecutiveSummaryProps) {
    if (!summary) return null

    const { riskDrivers, opportunityHighlights, ebitdaUplift } = summary

    return (
        <section className="print-section print-section--break-before">
            <h2>Executive Summary</h2>

            {ebitdaUplift ? (
                <div
                    className="print-card"
                    style={{
                        padding: '16px 20px',
                        marginBottom: '24px',
                        background: 'var(--bg-surface-3)',
                        borderRadius: '8px',
                        border: '1px solid var(--border-subtle)',
                    }}
                >
                    <div
                        style={{
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            color: 'var(--text-tertiary)',
                            textTransform: 'uppercase',
                            letterSpacing: '0.06em',
                            marginBottom: '12px',
                        }}
                    >
                        EBITDA Impact at a Glance
                    </div>
                    <div
                        style={{
                            display: 'flex',
                            flexWrap: 'wrap',
                            gap: '12px',
                            marginBottom: ebitdaUplift.summary ? '12px' : 0,
                        }}
                    >
                        {ebitdaUplift.revenueEstimate ? (
                            <span className="badge badge-low">Revenue: {ebitdaUplift.revenueEstimate}</span>
                        ) : null}
                        {ebitdaUplift.ebitdaEstimate ? (
                            <span className="badge badge-blue">EBITDA: {ebitdaUplift.ebitdaEstimate}</span>
                        ) : null}
                    </div>
                    {ebitdaUplift.summary ? (
                        <p
                            style={{
                                fontSize: '0.875rem',
                                lineHeight: 1.6,
                                color: 'var(--text-secondary)',
                                margin: 0,
                            }}
                        >
                            {ebitdaUplift.summary}
                        </p>
                    ) : null}
                </div>
            ) : null}

            {opportunityHighlights.length > 0 ? (
                <div style={{ marginBottom: '24px' }}>
                    <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: '0 0 12px' }}>
                        Top Opportunities
                    </h3>
                    <ol
                        style={{
                            margin: 0,
                            paddingLeft: '24px',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '8px',
                        }}
                    >
                        {opportunityHighlights.map((line) => (
                            <li
                                key={line.printedIndex}
                                style={{
                                    fontSize: '0.9rem',
                                    lineHeight: 1.6,
                                    color: 'var(--text-primary)',
                                }}
                            >
                                <strong>{line.title}</strong>
                                <span style={{ color: 'var(--text-secondary)' }}>
                                    {line.investmentRange ? ` — ${line.investmentRange}` : ''}
                                    {' · '}
                                    {line.timeline}
                                    {' · '}
                                    {line.impactRating} impact
                                </span>
                            </li>
                        ))}
                    </ol>
                </div>
            ) : null}

            {riskDrivers.length > 0 ? (
                <div>
                    <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: '0 0 12px' }}>
                        Why this score
                    </h3>
                    <ul
                        style={{
                            listStyle: 'none',
                            margin: 0,
                            padding: 0,
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '8px',
                        }}
                    >
                        {riskDrivers.map((driver) => {
                            const tier = getRiskTier(driver.score)
                            const color = TIER_COLORS[tier] ?? 'var(--text-secondary)'
                            return (
                                <li
                                    key={driver.category}
                                    style={{
                                        display: 'flex',
                                        gap: '12px',
                                        alignItems: 'baseline',
                                        fontSize: '0.9rem',
                                        lineHeight: 1.6,
                                    }}
                                >
                                    <span
                                        style={{
                                            color,
                                            fontWeight: 700,
                                            minWidth: '24px',
                                        }}
                                    >
                                        {driver.score}
                                    </span>
                                    <span>
                                        <strong>{driver.label}: </strong>
                                        <span style={{ color: 'var(--text-secondary)' }}>
                                            {driver.rationaleFirstSentence || 'No rationale provided.'}
                                        </span>
                                    </span>
                                </li>
                            )
                        })}
                    </ul>
                </div>
            ) : null}
        </section>
    )
}
