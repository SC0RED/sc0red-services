import { findByOriginalIndex, type OpportunityWithIndex } from '@/lib/pdf/sortOpportunities'
import type {
    CapacityObjective,
    CustomerObjective,
    FinancialObjective,
    InternalProcessTheme,
} from '@/lib/types/api'

/**
 * Per-perspective objective renderers for the print strategy map.
 *
 * Extracted from `PrintStrategyMap.tsx` to keep that file under the
 * 360-line limit. Each component is a thin wrapper around the shared
 * `PrintObjectiveCard` that knows how to format its specific
 * perspective's data shape.
 *
 * Phase 6 of ``redesign-analysis-visuals`` (design D6) updated print
 * parity:
 *   - confidence chip dropped from every card (matches the screen
 *     change in P2),
 *   - opportunity-link callout added, formatted as
 *     ``Opportunities: #N (title), #M (title)``. References the
 *     printed index from ``sortedOpportunities`` so a reader can flip
 *     from an objective to the matching opportunity card.
 */

export function ObjectivesGrid({ columns, children }: { columns: number; children: React.ReactNode }) {
    return (
        <div
            style={{
                display: 'grid',
                gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
                gap: '8px',
            }}
        >
            {children}
        </div>
    )
}

interface PerspectiveProps<T> {
    objective: T
    sortedOpportunities: OpportunityWithIndex[]
}

export function PrintFinancialObjective({
    objective,
    sortedOpportunities,
}: PerspectiveProps<FinancialObjective>) {
    return (
        <PrintObjectiveCard
            id={objective.id}
            title={objective.title}
            definition={objective.definition}
            linkedIndices={objective.linked_opportunity_indices ?? []}
            sortedOpportunities={sortedOpportunities}
        />
    )
}

export function PrintCustomerObjective({
    objective,
    sortedOpportunities,
}: PerspectiveProps<CustomerObjective>) {
    return (
        <PrintObjectiveCard
            id={objective.id}
            title={`"${objective.title}"`}
            definition={objective.definition}
            linkedIndices={objective.linked_opportunity_indices ?? []}
            sortedOpportunities={sortedOpportunities}
            italic
        />
    )
}

export function PrintInternalProcessTheme({
    theme,
    sortedOpportunities,
}: {
    theme: InternalProcessTheme
    sortedOpportunities: OpportunityWithIndex[]
}) {
    return (
        <div style={{ marginBottom: '12px' }}>
            <div
                style={{
                    fontSize: '0.65rem',
                    fontWeight: 700,
                    color: 'var(--text-tertiary)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    marginBottom: '4px',
                }}
            >
                {theme.name}
                {theme.supports_financial_objectives.length > 0
                    ? ` → ${theme.supports_financial_objectives.join(', ')}`
                    : ''}
            </div>
            <ObjectivesGrid columns={theme.objectives.length}>
                {theme.objectives.map((objective) => (
                    <PrintObjectiveCard
                        key={objective.id}
                        id={objective.id}
                        title={objective.title}
                        definition={objective.definition}
                        linkedIndices={objective.linked_opportunity_indices ?? []}
                        sortedOpportunities={sortedOpportunities}
                    />
                ))}
            </ObjectivesGrid>
        </div>
    )
}

export function PrintCapacityObjective({
    bucket,
    objective,
    sortedOpportunities,
}: {
    bucket: string
    objective: CapacityObjective
    sortedOpportunities: OpportunityWithIndex[]
}) {
    return (
        <div>
            <div
                style={{
                    fontSize: '0.65rem',
                    fontWeight: 700,
                    color: 'var(--accent-blue)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    marginBottom: '4px',
                }}
            >
                {bucket}
            </div>
            <PrintObjectiveCard
                id={objective.id}
                title={objective.title}
                definition={objective.definition}
                linkedIndices={objective.linked_opportunity_indices ?? []}
                sortedOpportunities={sortedOpportunities}
            />
        </div>
    )
}

/**
 * Shared objective card used by every perspective in the print
 * strategy map. Smaller and denser than the screen
 * `ObjectiveCard` — paper-friendly typography, no hover states,
 * fully-expanded definitions.
 *
 * Confidence chip removed in P2 of the redesign-analysis-visuals
 * change; the linked-opportunities callout below the description is
 * the new signal carrying value-of-this-objective information.
 */
function PrintObjectiveCard({
    id,
    title,
    definition,
    linkedIndices,
    sortedOpportunities,
    italic = false,
}: {
    id: string
    title: string
    definition: string
    linkedIndices: number[]
    sortedOpportunities: OpportunityWithIndex[]
    italic?: boolean
}) {
    const links = linkedIndices
        .map((originalIndex) => findByOriginalIndex(sortedOpportunities, originalIndex))
        .filter((entry): entry is OpportunityWithIndex => entry != null)

    return (
        <div
            className="print-card"
            style={{
                padding: '8px 10px',
                background: 'var(--bg-surface-2)',
                borderRadius: '4px',
                border: '1px solid var(--border-subtle)',
                fontSize: '0.75rem',
                lineHeight: 1.6,
            }}
        >
            <div
                style={{
                    display: 'flex',
                    alignItems: 'baseline',
                    gap: '6px',
                    marginBottom: '4px',
                }}
            >
                <span
                    style={{
                        fontFamily: 'var(--font-mono, monospace)',
                        fontSize: '0.65rem',
                        color: 'var(--text-tertiary)',
                    }}
                >
                    {id}
                </span>
                <strong
                    style={{
                        fontSize: '0.78rem',
                        fontStyle: italic ? 'italic' : 'normal',
                        flex: 1,
                    }}
                >
                    {title}
                </strong>
            </div>
            <p
                style={{
                    margin: 0,
                    fontSize: '0.7rem',
                    color: 'var(--text-secondary)',
                    fontStyle: italic ? 'italic' : 'normal',
                }}
            >
                {definition}
            </p>
            {links.length > 0 ? (
                <div
                    style={{
                        marginTop: '6px',
                        fontSize: '0.7rem',
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
        </div>
    )
}
