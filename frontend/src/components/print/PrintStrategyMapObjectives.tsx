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

export function PrintFinancialObjective({ objective }: { objective: FinancialObjective }) {
    return (
        <PrintObjectiveCard
            id={objective.id}
            title={objective.title}
            definition={objective.definition}
            confidence={objective.confidence}
        />
    )
}

export function PrintCustomerObjective({ objective }: { objective: CustomerObjective }) {
    return (
        <PrintObjectiveCard
            id={objective.id}
            title={`"${objective.title}"`}
            definition={objective.definition}
            confidence={objective.confidence}
            italic
        />
    )
}

export function PrintInternalProcessTheme({ theme }: { theme: InternalProcessTheme }) {
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
                        confidence={objective.confidence}
                    />
                ))}
            </ObjectivesGrid>
        </div>
    )
}

export function PrintCapacityObjective({
    bucket,
    objective,
}: {
    bucket: string
    objective: CapacityObjective
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
                confidence={objective.confidence}
            />
        </div>
    )
}

/**
 * Shared objective card used by every perspective in the print
 * strategy map. Smaller and denser than the screen
 * `ObjectiveCard` — paper-friendly typography, no hover states,
 * fully-expanded definitions.
 */
function PrintObjectiveCard({
    id,
    title,
    definition,
    confidence,
    italic = false,
}: {
    id: string
    title: string
    definition: string
    confidence: 'HIGH' | 'MEDIUM' | 'LOW'
    italic?: boolean
}) {
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
                <span
                    style={{
                        fontSize: '0.6rem',
                        fontWeight: 700,
                        color: 'var(--text-tertiary)',
                        letterSpacing: '0.04em',
                    }}
                >
                    {confidence}
                </span>
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
        </div>
    )
}
