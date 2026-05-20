import OpportunityDotStrip from '@/components/analysis/OpportunityDotStrip'
import { findByOriginalIndex, type OpportunityWithIndex } from '@/lib/pdf/sortOpportunities'
import { CAT_LABELS, RISK_CATEGORY_COLORS } from '@/lib/utils/riskUtils'
import type { Opportunity, ValueChain, ValueChainStep } from '@/lib/types/api'

interface PrintValueChainListProps {
    valueChain: ValueChain
    sortedOpportunities: OpportunityWithIndex[]
    /** Full opportunities array in original-index order — used by the
     *  shared ``OpportunityDotStrip`` to colour each dot from the
     *  linked opportunity's ``value_lever``. The print path additionally
     *  surfaces opportunity titles below the dot strip since print has
     *  no hover affordance. */
    opportunities: Opportunity[]
}

/**
 * Value Chain Analysis section — vertically stacked rows, primary
 * activities first, then support activities. Replaces the screen
 * `ValueChainDiagram`'s horizontal flex layout, which truncated mid-
 * row at A4 width on real value chains (six primary activities × full
 * label + chips never fit).
 *
 * Each row shows the activity name, role description, risk-category
 * chips, the shared ``OpportunityDotStrip`` (colour-per-lever signal),
 * AND a "Linked opportunities" callout listing the opportunity titles
 * with their printed-PDF-card index so cross-references stay stable.
 * The screen variant relies on hover tooltips for the titles; print
 * has no hover, so titles + dots both render here.
 */
export default function PrintValueChainList({
    valueChain,
    sortedOpportunities,
    opportunities,
}: PrintValueChainListProps) {
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
                    opportunities={opportunities}
                />
            ) : null}

            {support.length > 0 ? (
                <ChainGroup
                    title="Support Activities"
                    steps={support}
                    sortedOpportunities={sortedOpportunities}
                    opportunities={opportunities}
                />
            ) : null}
        </section>
    )
}

interface ChainGroupProps {
    title: string
    steps: ValueChainStep[]
    sortedOpportunities: OpportunityWithIndex[]
    opportunities: Opportunity[]
}

function ChainGroup({ title, steps, sortedOpportunities, opportunities }: ChainGroupProps) {
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
                    <ChainRow
                        key={step.id}
                        step={step}
                        sortedOpportunities={sortedOpportunities}
                        opportunities={opportunities}
                    />
                ))}
            </ol>
        </div>
    )
}

function ChainRow({
    step,
    sortedOpportunities,
    opportunities,
}: {
    step: ValueChainStep
    sortedOpportunities: OpportunityWithIndex[]
    opportunities: Opportunity[]
}) {
    const indices = step.opportunity_indices ?? []
    const links = indices
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
            {/* Opportunity-link dot strip — same shared component as the
                screen variant. Print has no hover, so the title list
                below still renders explicitly. */}
            {indices.length > 0 ? (
                <OpportunityDotStrip
                    linkedIndices={indices}
                    opportunities={opportunities}
                    testId={`print-value-chain-linked-opportunity-dots-${step.id}`}
                />
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
