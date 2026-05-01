import { LEVER_COLORS } from '@/lib/utils/leverColors'
import type { Opportunity } from '@/lib/types/api'

interface PrintOpportunityCardProps {
    opportunity: Opportunity
    /** 1-based position in the printed PDF; used for cross-section linkage. */
    printedIndex: number
}

/**
 * One opportunity rendered fully expanded — every populated field is
 * visible in the document. No expand/collapse control; no badges-only
 * preview. Designed to occupy roughly half a page so two cards fit per
 * page when content is short, with `page-break-inside: avoid` to keep
 * each card together.
 *
 * Print-only counterpart to the cards inside `OpportunitiesList`. The
 * screen list collapses-by-default; that's the bug we are fixing here.
 */
export default function PrintOpportunityCard({ opportunity, printedIndex }: PrintOpportunityCardProps) {
    const leverColor = opportunity.value_lever
        ? (LEVER_COLORS[opportunity.value_lever] ?? 'var(--text-secondary)')
        : null

    return (
        <article
            className="print-opportunity-card"
            style={{
                padding: '18px 20px',
                background: 'var(--bg-surface-2)',
                border: '1px solid var(--border-subtle)',
                borderLeft: leverColor ? `4px solid ${leverColor}` : '1px solid var(--border-subtle)',
                borderRadius: '8px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
            }}
        >
            <header style={{ display: 'flex', alignItems: 'baseline', gap: '12px' }}>
                <span
                    style={{
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        color: 'var(--text-tertiary)',
                        flexShrink: 0,
                    }}
                >
                    #{printedIndex}
                </span>
                <h3
                    style={{
                        fontSize: '1rem',
                        fontWeight: 700,
                        margin: 0,
                        flex: 1,
                        lineHeight: 1.35,
                    }}
                >
                    {opportunity.title}
                </h3>
            </header>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                <span className="badge badge-low">{opportunity.impact_rating} Impact</span>
                <span className="badge badge-blue" style={{ fontSize: '0.7rem' }}>
                    {opportunity.timeline}
                </span>
                <span className="badge badge-neutral">{opportunity.strategic_category}</span>
                {opportunity.value_lever && leverColor ? (
                    <span
                        style={{
                            padding: '2px 10px',
                            borderRadius: '999px',
                            fontSize: '0.7rem',
                            fontWeight: 500,
                            border: `1px solid ${leverColor}`,
                            color: leverColor,
                        }}
                    >
                        {opportunity.value_lever}
                    </span>
                ) : null}
            </div>

            <p
                style={{
                    fontSize: '0.9rem',
                    lineHeight: 1.7,
                    color: 'var(--text-primary)',
                    margin: 0,
                    whiteSpace: 'pre-line',
                }}
            >
                {opportunity.description}
            </p>

            {opportunity.implementation_steps && opportunity.implementation_steps.length > 0 ? (
                <div>
                    <div
                        style={{
                            fontSize: '0.7rem',
                            fontWeight: 600,
                            color: 'var(--text-tertiary)',
                            textTransform: 'uppercase',
                            letterSpacing: '0.06em',
                            marginBottom: '8px',
                        }}
                    >
                        Implementation Steps
                    </div>
                    <ol
                        style={{
                            margin: 0,
                            paddingLeft: '24px',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '6px',
                        }}
                    >
                        {opportunity.implementation_steps.map((step, idx) => (
                            <li
                                key={idx}
                                style={{
                                    fontSize: '0.85rem',
                                    lineHeight: 1.6,
                                    color: 'var(--text-primary)',
                                }}
                            >
                                {step}
                            </li>
                        ))}
                    </ol>
                </div>
            ) : null}

            {opportunity.investment_range || opportunity.roi_estimate ? (
                <div
                    style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        gap: '12px',
                    }}
                >
                    {opportunity.investment_range ? (
                        <div
                            style={{
                                padding: '10px 12px',
                                background: 'var(--bg-surface-3)',
                                borderRadius: '6px',
                                borderLeft: '3px solid var(--risk-moderate)',
                            }}
                        >
                            <div
                                style={{
                                    fontSize: '0.7rem',
                                    fontWeight: 600,
                                    color: 'var(--text-tertiary)',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.06em',
                                    marginBottom: '4px',
                                }}
                            >
                                Estimated Investment
                            </div>
                            <div style={{ fontWeight: 700, color: 'var(--risk-moderate)' }}>
                                {opportunity.investment_range}
                            </div>
                        </div>
                    ) : null}
                    {opportunity.roi_estimate ? (
                        <div
                            style={{
                                padding: '10px 12px',
                                background: 'var(--bg-surface-3)',
                                borderRadius: '6px',
                                borderLeft: '3px solid var(--risk-low)',
                            }}
                        >
                            <div
                                style={{
                                    fontSize: '0.7rem',
                                    fontWeight: 600,
                                    color: 'var(--text-tertiary)',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.06em',
                                    marginBottom: '4px',
                                }}
                            >
                                Potential ROI
                            </div>
                            <div
                                style={{
                                    fontWeight: 600,
                                    color: 'var(--risk-low)',
                                    fontSize: '0.85rem',
                                }}
                            >
                                {opportunity.roi_estimate}
                            </div>
                        </div>
                    ) : null}
                </div>
            ) : null}
        </article>
    )
}
