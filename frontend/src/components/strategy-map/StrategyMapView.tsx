import type { StrategyMap } from '@/lib/types/api'
import { formatValueProposition } from '@/lib/utils/strategyMapUtils'

import {
    CustomerPerspectiveRow,
    FinancialPerspectiveRow,
    InternalProcessesPerspectiveRow,
    OrganizationalCapacityRow,
} from './PerspectiveRow'
import WhatsMissingPanel from './WhatsMissingPanel'

interface StrategyMapViewProps {
    strategyMap: StrategyMap
}

/**
 * AI-generated Balanced Scorecard strategy map for the rebranded
 * Vector Advisory product. Renders at the top of the analysis page
 * (position 3, immediately after AnalysisHeader + AnalysisOverviewCards).
 *
 * Layout follows the BSCi visual template:
 *   - Header band: Vision, Mission, Customer Value Proposition,
 *     Strategic Priorities (3 themed columns)
 *   - The four perspectives (read top → bottom):
 *       Financial → Customer → Internal Processes → Organizational
 *       Capacity, with narrative connector phrases between
 *   - Core values strip at the bottom
 *   - "What's Missing?" panel below the map
 *
 * The deep-dive CTA is rendered separately by `AnalysisDetail`
 * directly below this component, so it appears right after the gaps.
 *
 * Read-only in v1; no editing UI.
 */
export default function StrategyMapView({ strategyMap }: StrategyMapViewProps) {
    return (
        <section
            data-testid="strategy-map-view"
            className="strategy-map"
            style={{
                marginBottom: '24px',
                padding: '20px',
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '20px',
            }}
        >
            <Header strategyMap={strategyMap} />
            <FinancialPerspectiveRow objectives={strategyMap.financial.objectives} />
            <CustomerPerspectiveRow objectives={strategyMap.customer.objectives} />
            <InternalProcessesPerspectiveRow themes={strategyMap.internalProcesses.themes} />
            <OrganizationalCapacityRow perspective={strategyMap.organizationalCapacity} />
            <CoreValuesStrip
                values={strategyMap.coreValues.values}
                synthesised={strategyMap.coreValues.synthesised}
            />
            <WhatsMissingPanel gaps={strategyMap.whatsMissing} />
        </section>
    )
}

// ── Header band: vision / mission / value-prop / strategic priorities ────

function Header({ strategyMap }: { strategyMap: StrategyMap }) {
    const { vision, mission, valueProposition, strategicPriorities } = strategyMap
    return (
        <header
            style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '14px',
                paddingBottom: '14px',
                borderBottom: '1px solid var(--border-subtle)',
            }}
        >
            <div
                style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    color: 'var(--accent-blue)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                }}
            >
                Strategy Map
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <div
                    style={{
                        fontSize: '0.7rem',
                        color: 'var(--text-tertiary)',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                    }}
                >
                    Vision {vision.synthesised ? '(synthesised)' : ''}
                </div>
                <p
                    style={{
                        fontSize: '1.1rem',
                        fontStyle: 'italic',
                        margin: 0,
                        color: 'var(--text-primary)',
                        lineHeight: 1.4,
                    }}
                >
                    &ldquo;{vision.statement}&rdquo;
                </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div
                    style={{
                        fontSize: '0.7rem',
                        color: 'var(--text-tertiary)',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                    }}
                >
                    Mission {mission.synthesised ? '(synthesised)' : ''}
                </div>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.6 }}>
                    {mission.statement}
                </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <span
                    style={{
                        fontSize: '0.7rem',
                        color: 'var(--text-tertiary)',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                    }}
                >
                    Value Proposition:
                </span>
                <ValuePropositionChip
                    primary={valueProposition.primary}
                    secondary={valueProposition.secondary}
                />
                <span
                    style={{
                        fontSize: '0.8rem',
                        color: 'var(--text-secondary)',
                        fontStyle: 'italic',
                    }}
                >
                    {valueProposition.rationale}
                </span>
            </div>

            {strategicPriorities.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <div
                        style={{
                            fontSize: '0.7rem',
                            color: 'var(--text-tertiary)',
                            fontWeight: 600,
                            textTransform: 'uppercase',
                            letterSpacing: '0.06em',
                        }}
                    >
                        Strategic Priorities
                    </div>
                    <div
                        style={{
                            display: 'grid',
                            gridTemplateColumns: `repeat(${strategicPriorities.length}, minmax(0, 1fr))`,
                            gap: '12px',
                        }}
                    >
                        {strategicPriorities.map((priority) => (
                            <div
                                key={priority.name}
                                style={{
                                    padding: '10px 12px',
                                    background: 'var(--bg-surface-2)',
                                    borderRadius: '6px',
                                    borderTop: '3px solid var(--accent-blue)',
                                }}
                            >
                                <div
                                    style={{
                                        fontSize: '0.85rem',
                                        fontWeight: 700,
                                        marginBottom: '4px',
                                        color: 'var(--text-primary)',
                                    }}
                                >
                                    {priority.name}
                                </div>
                                <div
                                    style={{
                                        fontSize: '0.75rem',
                                        lineHeight: 1.5,
                                        color: 'var(--text-secondary)',
                                    }}
                                >
                                    {priority.result}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            ) : null}
        </header>
    )
}

function ValuePropositionChip({
    primary,
    secondary,
}: {
    primary: StrategyMap['valueProposition']['primary']
    secondary?: StrategyMap['valueProposition']['secondary']
}) {
    const label = formatValueProposition(primary, secondary)
    return (
        <span
            style={{
                display: 'inline-flex',
                padding: '3px 10px',
                borderRadius: '999px',
                fontSize: '0.75rem',
                fontWeight: 700,
                background: 'var(--accent-blue-glow)',
                color: 'var(--accent-blue)',
                border: '1px solid var(--accent-blue)',
                letterSpacing: '0.02em',
            }}
        >
            {label}
        </span>
    )
}

// ── Core values strip ─────────────────────────────────────────────────────

function CoreValuesStrip({ values, synthesised }: { values: string[]; synthesised: boolean }) {
    return (
        <div
            style={{
                padding: '10px 14px',
                background: 'var(--bg-surface-3)',
                borderRadius: '6px',
                fontSize: '0.85rem',
                color: 'var(--text-secondary)',
                textAlign: 'center',
            }}
        >
            <span
                style={{
                    fontSize: '0.7rem',
                    color: 'var(--text-tertiary)',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    marginRight: '8px',
                }}
            >
                Live our values{synthesised ? ' (inferred)' : ''}:
            </span>
            {values.join(' · ')}
        </div>
    )
}
