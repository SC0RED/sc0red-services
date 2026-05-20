import ProvenanceMarker from '@/components/analysis/ProvenanceMarker'
import type { OpportunityWithIndex } from '@/lib/pdf/sortOpportunities'
import type { StrategyMap } from '@/lib/types/api'
import { formatValueProposition } from '@/lib/utils/strategyMapUtils'

import {
    ObjectivesGrid,
    PrintCapacityObjective,
    PrintCustomerObjective,
    PrintFinancialObjective,
    PrintInternalProcessTheme,
} from './PrintStrategyMapObjectives'

interface PrintStrategyMapProps {
    strategyMap: StrategyMap
    /** Same sorted-with-original-index list used elsewhere in the PDF.
     *  Required so each objective's ``linked_opportunity_indices`` can
     *  resolve to a printed-index reference (``#N (title)``). Print
     *  parity for the screen ``OpportunityDotStrip``. */
    sortedOpportunities: OpportunityWithIndex[]
}

/**
 * Print-only Balanced Scorecard strategy map.
 *
 * Parallel implementation to `StrategyMapView` — same content,
 * paper-friendly layout. No interactive elements, no hover states,
 * fully-expanded definitions visible inline. The deep-dive CTA does
 * NOT render here — the PDF's back cover (`PrintBackCover`) is the
 * single conversion surface in print.
 *
 * Section position: first content section after `PrintExecutiveSummary`,
 * before `TopActionsCallout`. Sits behind a `print-section--break-before`
 * so it always starts on a fresh page.
 *
 * Per-perspective objective rendering lives in
 * `PrintStrategyMapObjectives.tsx`; this file is the composition root
 * plus the shared header / connector / values / gaps blocks.
 */
export default function PrintStrategyMap({ strategyMap, sortedOpportunities }: PrintStrategyMapProps) {
    return (
        <section className="print-section print-section--break-before print-strategy-map">
            <h2>Strategy Map</h2>

            <PrintHeader strategyMap={strategyMap} />

            <PrintPerspective label="Financial" tagline="Returns we generate">
                <ObjectivesGrid columns={strategyMap.financial.objectives.length}>
                    {strategyMap.financial.objectives.map((objective) => (
                        <PrintFinancialObjective
                            key={objective.id}
                            objective={objective}
                            sortedOpportunities={sortedOpportunities}
                        />
                    ))}
                </ObjectivesGrid>
            </PrintPerspective>

            <PrintPerspective
                label="Customer"
                tagline="What customers experience"
                connectorAbove="Which simplify the lives of our…"
            >
                <ObjectivesGrid columns={Math.min(strategyMap.customer.objectives.length, 4)}>
                    {strategyMap.customer.objectives.map((objective) => (
                        <PrintCustomerObjective
                            key={objective.id}
                            objective={objective}
                            sortedOpportunities={sortedOpportunities}
                        />
                    ))}
                </ObjectivesGrid>
            </PrintPerspective>

            <PrintPerspective
                label="Internal Processes"
                tagline="What we do operationally"
                connectorAbove="Enables us to deliver"
            >
                {strategyMap.internalProcesses.themes.map((theme) => (
                    <PrintInternalProcessTheme
                        key={theme.name}
                        theme={theme}
                        sortedOpportunities={sortedOpportunities}
                    />
                ))}
            </PrintPerspective>

            <PrintPerspective
                label="Organizational Capacity"
                tagline="People, technology, culture"
                connectorAbove="Live our values"
            >
                <ObjectivesGrid columns={3}>
                    <PrintCapacityObjective
                        bucket="People"
                        objective={strategyMap.organizationalCapacity.people}
                        sortedOpportunities={sortedOpportunities}
                    />
                    <PrintCapacityObjective
                        bucket="Technology"
                        objective={strategyMap.organizationalCapacity.technology}
                        sortedOpportunities={sortedOpportunities}
                    />
                    <PrintCapacityObjective
                        bucket="Culture"
                        objective={strategyMap.organizationalCapacity.culture}
                        sortedOpportunities={sortedOpportunities}
                    />
                </ObjectivesGrid>
            </PrintPerspective>

            <PrintCoreValuesStrip
                values={strategyMap.coreValues.values}
                synthesised={strategyMap.coreValues.synthesised}
            />
        </section>
    )
}

// ── Header ───────────────────────────────────────────────────────────────

function PrintHeader({ strategyMap }: { strategyMap: StrategyMap }) {
    const { vision, mission, valueProposition, strategicPriorities } = strategyMap
    return (
        <div style={{ marginBottom: '20px' }}>
            <p style={{ fontSize: '0.95rem', fontStyle: 'italic', margin: '0 0 6px' }}>
                <strong>Vision:</strong> &ldquo;{vision.statement}&rdquo;
                {vision.synthesised ? (
                    <span style={{ marginLeft: '6px', fontStyle: 'normal' }}>
                        <ProvenanceMarker kind="inferred" />
                    </span>
                ) : null}
            </p>
            <p style={{ fontSize: '0.85rem', margin: '0 0 6px', color: 'var(--text-secondary)' }}>
                <strong>Mission:</strong> {mission.statement}
                {mission.synthesised ? (
                    <span style={{ marginLeft: '6px' }}>
                        <ProvenanceMarker kind="inferred" />
                    </span>
                ) : null}
            </p>
            <p style={{ fontSize: '0.85rem', margin: '0 0 10px', color: 'var(--text-secondary)' }}>
                <strong>Value Proposition:</strong>{' '}
                {formatValueProposition(valueProposition.primary, valueProposition.secondary)} —{' '}
                <em>{valueProposition.rationale}</em>
            </p>
            {strategicPriorities.length > 0 ? (
                <div
                    style={{
                        display: 'grid',
                        gridTemplateColumns: `repeat(${strategicPriorities.length}, minmax(0, 1fr))`,
                        gap: '8px',
                        marginTop: '10px',
                    }}
                >
                    {strategicPriorities.map((priority) => (
                        <div
                            key={priority.name}
                            className="print-card"
                            style={{
                                padding: '8px 10px',
                                background: 'var(--bg-surface-3)',
                                borderTop: '2px solid var(--accent-blue)',
                                borderRadius: '4px',
                            }}
                        >
                            <div style={{ fontSize: '0.8rem', fontWeight: 700 }}>{priority.name}</div>
                            <div
                                style={{
                                    fontSize: '0.7rem',
                                    color: 'var(--text-secondary)',
                                    lineHeight: 1.5,
                                }}
                            >
                                {priority.result}
                            </div>
                        </div>
                    ))}
                </div>
            ) : null}
        </div>
    )
}

// ── Perspective container ────────────────────────────────────────────────

function PrintPerspective({
    label,
    tagline,
    connectorAbove,
    children,
}: {
    label: string
    tagline: string
    connectorAbove?: string
    children: React.ReactNode
}) {
    return (
        <div className="print-strategy-map-perspective" style={{ marginBottom: '14px' }}>
            {connectorAbove ? (
                <div
                    style={{
                        textAlign: 'center',
                        fontSize: '0.7rem',
                        color: 'var(--text-tertiary)',
                        fontStyle: 'italic',
                        marginBottom: '4px',
                    }}
                >
                    ↑ {connectorAbove} ↑
                </div>
            ) : null}
            <div
                style={{
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    color: 'var(--text-tertiary)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    marginBottom: '6px',
                }}
            >
                {label} <span style={{ fontWeight: 400 }}>· {tagline}</span>
            </div>
            {children}
        </div>
    )
}

// ── Core values strip ────────────────────────────────────────────────────

function PrintCoreValuesStrip({ values, synthesised }: { values: string[]; synthesised: boolean }) {
    return (
        <div
            style={{
                marginTop: '10px',
                padding: '6px 10px',
                background: 'var(--bg-surface-3)',
                borderRadius: '4px',
                fontSize: '0.7rem',
                textAlign: 'center',
                color: 'var(--text-secondary)',
            }}
        >
            <strong>Live our values: </strong>
            {values.join(' · ')}
            {synthesised ? (
                <span style={{ marginLeft: '6px' }}>
                    <ProvenanceMarker kind="inferred" />
                </span>
            ) : null}
        </div>
    )
}
