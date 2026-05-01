import { findByOriginalIndex, type OpportunityWithIndex } from '@/lib/pdf/sortOpportunities'
import { CAT_LABELS, RISK_CATEGORY_COLORS } from '@/lib/utils/riskUtils'
import type { ValueChain, ValueChainStep } from '@/lib/types/api'

interface PrintValueChainListProps {
    valueChain: ValueChain
    sortedOpportunities: OpportunityWithIndex[]
}

/**
 * Value Chain Analysis section — vertically stacked rows, primary
 * activities first, then support activities. Replaces the screen
 * `ValueChainDiagram`'s horizontal flex layout, which truncated mid-
 * row at A4 width on real value chains (six primary activities × full
 * label + chips never fit).
 *
 * Each row shows the activity name, role description, risk-category
 * chips, and a "Linked opportunities" callout (using the sorted-PDF-
 * index of each opportunity card so cross-references stay stable).
 */
export default function PrintValueChainList({ valueChain, sortedOpportunities }: PrintValueChainListProps) {
    if (!valueChain.steps.length) return null

    const primary = valueChain.steps.filter((step) => step.category === 'primary')
    const support = valueChain.steps.filter((step) => step.category === 'support')

    return (
        <section className="print-section print-section--break-before">
            <h2>Value Chain Analysis</h2>

            {valueChain.summary ? (
                <p
                    style={{
                        fontSize: '0.9rem',
                        lineHeight: 1.7,
                        color: 'var(--text-secondary)',
                        marginBottom: '20px',
                    }}
                >
                    {valueChain.summary}
                </p>
            ) : null}

            {primary.length > 0 ? (
                <ChainGroup
                    title="Primary Activities"
                    steps={primary}
                    sortedOpportunities={sortedOpportunities}
                />
            ) : null}

            {support.length > 0 ? (
                <ChainGroup
                    title="Support Activities"
                    steps={support}
                    sortedOpportunities={sortedOpportunities}
                />
            ) : null}
        </section>
    )
}

interface ChainGroupProps {
    title: string
    steps: ValueChainStep[]
    sortedOpportunities: OpportunityWithIndex[]
}

function ChainGroup({ title, steps, sortedOpportunities }: ChainGroupProps) {
    return (
        <div style={{ marginBottom: '24px' }}>
            <h3
                style={{
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    color: 'var(--text-tertiary)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                    margin: '0 0 12px',
                }}
            >
                {title}
            </h3>
            <ol
                style={{
                    listStyle: 'none',
                    margin: 0,
                    padding: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                    counterReset: 'chain-step',
                }}
            >
                {steps.map((step) => (
                    <ChainRow key={step.id} step={step} sortedOpportunities={sortedOpportunities} />
                ))}
            </ol>
        </div>
    )
}

function ChainRow({
    step,
    sortedOpportunities,
}: {
    step: ValueChainStep
    sortedOpportunities: OpportunityWithIndex[]
}) {
    const links = (step.opportunity_indices ?? [])
        .map((originalIndex) => findByOriginalIndex(sortedOpportunities, originalIndex))
        .filter((entry): entry is OpportunityWithIndex => entry != null)

    return (
        <li
            className="print-value-chain-row"
            style={{
                padding: '14px 16px',
                background: 'var(--bg-surface-2)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
            }}
        >
            <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>{step.label}</div>
            {step.description ? (
                <p
                    style={{
                        fontSize: '0.85rem',
                        lineHeight: 1.6,
                        color: 'var(--text-secondary)',
                        margin: 0,
                    }}
                >
                    {step.description}
                </p>
            ) : null}
            {step.risk_categories.length > 0 ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {step.risk_categories.map((category) => {
                        const color = RISK_CATEGORY_COLORS[category] ?? 'var(--text-tertiary)'
                        return (
                            <span
                                key={category}
                                style={{
                                    fontSize: '0.65rem',
                                    fontWeight: 500,
                                    padding: '2px 8px',
                                    borderRadius: '999px',
                                    background: `${color}15`,
                                    color,
                                    border: `1px solid ${color}30`,
                                }}
                            >
                                {CAT_LABELS[category] ?? category}
                            </span>
                        )
                    })}
                </div>
            ) : null}
            {links.length > 0 ? (
                <div
                    style={{
                        fontSize: '0.75rem',
                        color: 'var(--accent-blue)',
                        lineHeight: 1.5,
                    }}
                >
                    Opportunities:{' '}
                    {links.map((link, idx) => (
                        <span key={link.printedIndex}>
                            #{link.printedIndex} ({link.opportunity.title})
                            {idx < links.length - 1 ? ', ' : ''}
                        </span>
                    ))}
                </div>
            ) : null}
        </li>
    )
}
