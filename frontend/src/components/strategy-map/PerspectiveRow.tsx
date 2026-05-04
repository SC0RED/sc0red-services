import type {
    CapacityObjective,
    CustomerObjective,
    FinancialObjective,
    InternalProcessTheme,
    OrganizationalCapacityPerspective,
} from '@/lib/types/api'
import ObjectiveCard from './ObjectiveCard'

/**
 * One row on the strategy map — renders the four perspective shapes:
 *
 *   Financial               flat list of imperative objectives
 *   Customer                cards in first-person customer voice
 *   Internal Processes      themed groups (2-3 named themes)
 *   Organizational Capacity People / Technology / Culture triad
 *
 * The narrative connector phrase between perspectives ("Enables us
 * to deliver" / "Which simplify the lives of our…" / "Who reward us
 * with…") is rendered by the parent `StrategyMapView` between rows
 * so the connectors live with the layout, not with the rows.
 */

const FINANCIAL_CATEGORY_COLORS: Record<FinancialObjective['category'], string> = {
    revenue_growth: 'var(--risk-low)',
    productivity: 'var(--accent-blue)',
}

const IP_CATEGORY_COLORS: Record<InternalProcessObjectiveCategory, string> = {
    innovation: 'var(--accent-blue)',
    customer_management: 'var(--risk-low)',
    operational_excellence: 'var(--risk-moderate)',
    citizenship: 'var(--text-tertiary)',
}

type InternalProcessObjectiveCategory =
    | 'innovation'
    | 'customer_management'
    | 'operational_excellence'
    | 'citizenship'

// ── Financial ─────────────────────────────────────────────────────────────

export function FinancialPerspectiveRow({ objectives }: { objectives: FinancialObjective[] }) {
    return (
        <PerspectiveContainer label="Financial" tagline="Returns we generate">
            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: `repeat(${objectives.length}, minmax(0, 1fr))`,
                    gap: '12px',
                }}
            >
                {objectives.map((objective) => (
                    <ObjectiveCard
                        key={objective.id}
                        id={objective.id}
                        title={objective.title}
                        definition={objective.definition}
                        confidence={objective.confidence}
                        accentColor={FINANCIAL_CATEGORY_COLORS[objective.category]}
                    />
                ))}
            </div>
        </PerspectiveContainer>
    )
}

// ── Customer ──────────────────────────────────────────────────────────────

export function CustomerPerspectiveRow({ objectives }: { objectives: CustomerObjective[] }) {
    return (
        <PerspectiveContainer
            label="Customer"
            tagline="What customers experience"
            connectorAbove="Which simplify the lives of our…"
        >
            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: `repeat(${Math.min(objectives.length, 4)}, minmax(0, 1fr))`,
                    gap: '12px',
                }}
            >
                {objectives.map((objective) => (
                    <ObjectiveCard
                        key={objective.id}
                        id={objective.id}
                        title={objective.title}
                        definition={objective.definition}
                        confidence={objective.confidence}
                        customerVoice
                    />
                ))}
            </div>
        </PerspectiveContainer>
    )
}

// ── Internal Processes (themed) ───────────────────────────────────────────

export function InternalProcessesPerspectiveRow({ themes }: { themes: InternalProcessTheme[] }) {
    return (
        <PerspectiveContainer
            label="Internal Processes"
            tagline="What we do operationally"
            connectorAbove="Enables us to deliver"
        >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
                {themes.map((theme) => (
                    <div key={theme.name}>
                        <div
                            style={{
                                display: 'flex',
                                alignItems: 'baseline',
                                justifyContent: 'space-between',
                                marginBottom: '8px',
                            }}
                        >
                            <h4
                                style={{
                                    fontSize: '0.7rem',
                                    fontWeight: 700,
                                    color: 'var(--text-tertiary)',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.08em',
                                    margin: 0,
                                }}
                            >
                                {theme.name}
                            </h4>
                            {theme.supports_financial_objectives.length > 0 ? (
                                <span
                                    style={{
                                        fontSize: '0.7rem',
                                        color: 'var(--text-tertiary)',
                                        fontFamily: 'var(--font-mono, monospace)',
                                    }}
                                >
                                    → {theme.supports_financial_objectives.join(', ')}
                                </span>
                            ) : null}
                        </div>
                        <div
                            style={{
                                display: 'grid',
                                gridTemplateColumns: `repeat(${theme.objectives.length}, minmax(0, 1fr))`,
                                gap: '12px',
                            }}
                        >
                            {theme.objectives.map((objective) => (
                                <ObjectiveCard
                                    key={objective.id}
                                    id={objective.id}
                                    title={objective.title}
                                    definition={objective.definition}
                                    confidence={objective.confidence}
                                    accentColor={IP_CATEGORY_COLORS[objective.category]}
                                />
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        </PerspectiveContainer>
    )
}

// ── Organizational Capacity (People / Technology / Culture) ───────────────

export function OrganizationalCapacityRow({
    perspective,
}: {
    perspective: OrganizationalCapacityPerspective
}) {
    const buckets: Array<{ label: string; objective: CapacityObjective }> = [
        { label: 'People', objective: perspective.people },
        { label: 'Technology', objective: perspective.technology },
        { label: 'Culture', objective: perspective.culture },
    ]
    return (
        <PerspectiveContainer
            label="Organizational Capacity"
            tagline="People, technology, culture"
            connectorAbove="Live our values"
        >
            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
                    gap: '12px',
                }}
            >
                {buckets.map(({ label, objective }) => (
                    <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <div
                            style={{
                                fontSize: '0.65rem',
                                fontWeight: 700,
                                color: 'var(--accent-blue)',
                                textTransform: 'uppercase',
                                letterSpacing: '0.08em',
                            }}
                        >
                            {label}
                        </div>
                        <ObjectiveCard
                            id={objective.id}
                            title={objective.title}
                            definition={objective.definition}
                            confidence={objective.confidence}
                            accentColor="var(--accent-blue)"
                        />
                    </div>
                ))}
            </div>
        </PerspectiveContainer>
    )
}

// ── Container with label + optional connector phrase ──────────────────────

interface PerspectiveContainerProps {
    label: string
    tagline: string
    connectorAbove?: string
    children: React.ReactNode
}

function PerspectiveContainer({ label, tagline, connectorAbove, children }: PerspectiveContainerProps) {
    return (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {connectorAbove ? (
                <div
                    style={{
                        textAlign: 'center',
                        fontSize: '0.7rem',
                        color: 'var(--text-tertiary)',
                        fontStyle: 'italic',
                        marginTop: '-4px',
                    }}
                >
                    ↑ {connectorAbove} ↑
                </div>
            ) : null}
            <header
                style={{
                    display: 'flex',
                    alignItems: 'baseline',
                    gap: '12px',
                    paddingBottom: '4px',
                    borderBottom: '1px solid var(--border-subtle)',
                }}
            >
                <h3
                    style={{
                        fontSize: '0.85rem',
                        fontWeight: 700,
                        margin: 0,
                        color: 'var(--text-primary)',
                    }}
                >
                    {label}
                </h3>
                <span
                    style={{
                        fontSize: '0.75rem',
                        color: 'var(--text-tertiary)',
                    }}
                >
                    {tagline}
                </span>
            </header>
            {children}
        </section>
    )
}
