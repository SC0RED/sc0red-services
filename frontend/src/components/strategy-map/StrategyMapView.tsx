'use client'

import ConfidenceIndicator from '@/components/analysis/ConfidenceIndicator'
import ProvenanceMarker from '@/components/analysis/ProvenanceMarker'
import type { ConfidenceMarker, StrategyMap } from '@/lib/types/api'

import StrategyMapCanvas from './StrategyMapCanvas'
import StrategyMapHeader from './StrategyMapHeader'

interface StrategyMapViewProps {
    strategyMap: StrategyMap
}

/**
 * AI-generated Balanced Scorecard strategy map.
 *
 * Composition root for the strategy-map section on the analysis page:
 *
 *   1. `StrategyMapHeader`       — vision, mission disclosure,
 *                                  value-prop chip, strategic-priority
 *                                  legend
 *   2. `StrategyMapCanvas`       — graphical 2D React Flow canvas
 *                                  with the four perspective bands,
 *                                  objective chips, and arrows
 *   3. `ConfidenceLegend`        — explains the three-dot confidence
 *                                  scale used on every chip
 *   4. `CoreValuesStrip`         — bottom strip listing the company's
 *                                  values
 *
 * The "What's Missing" / gaps panel was previously rendered below the
 * canvas; it has been removed end-to-end as part of the
 * ``redesign-strategy-map`` Phase 2 change. The deep-dive CTA was
 * previously rendered below this section; it has been relocated to
 * the top of `AnalysisDetail` (above the page).
 *
 * Print rendering uses `PrintStrategyMap.tsx` (untouched by this
 * redesign) — paper has no scroll constraint, the verbose layout is
 * the right artefact for print.
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
                gap: '16px',
            }}
        >
            <StrategyMapHeader strategyMap={strategyMap} />
            <StrategyMapCanvas strategyMap={strategyMap} />
            <ConfidenceLegend />
            <CoreValuesStrip
                values={strategyMap.coreValues.values}
                synthesised={strategyMap.coreValues.synthesised}
            />
        </section>
    )
}

/**
 * Inline legend explaining the confidence dots on each objective chip.
 *
 * Every chip on the canvas renders a ``small``-variant
 * ``ConfidenceIndicator``: 3 dots, partially filled, single neutral
 * colour. Without context the dots read as decorative — users have
 * to hover (and even then the small variant has no tooltip). This
 * legend sits directly under the canvas so the meaning is one glance
 * away. Each row reuses ``ConfidenceIndicator`` so the legend dots
 * are guaranteed pixel-identical to the chip dots; if the
 * indicator's rendering ever changes the legend follows automatically.
 */
function ConfidenceLegend() {
    const entries: { confidence: ConfidenceMarker; label: string; description: string }[] = [
        {
            confidence: 'HIGH',
            label: 'High',
            description: 'directly inferred from concrete public data.',
        },
        {
            confidence: 'MEDIUM',
            label: 'Medium',
            description: 'typical of similar companies; pattern-matched but not directly observed.',
        },
        {
            confidence: 'LOW',
            label: 'Low',
            description: 'inferred from absence; reasonable but unverified — deep-dive candidate.',
        },
    ]

    return (
        <div
            data-testid="strategy-map-confidence-legend"
            style={{
                padding: '10px 14px',
                background: 'var(--bg-surface-2)',
                borderRadius: '6px',
                fontSize: '0.75rem',
                color: 'var(--text-secondary)',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
            }}
        >
            <span
                style={{
                    fontSize: '0.75rem',
                    color: 'var(--text-tertiary)',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                }}
            >
                Confidence in each objective
            </span>
            <ul
                style={{
                    listStyle: 'none',
                    padding: 0,
                    margin: 0,
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '16px',
                }}
            >
                {entries.map(({ confidence, label, description }) => (
                    <li
                        key={confidence}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            flex: '1 1 240px',
                            minWidth: '240px',
                        }}
                    >
                        <ConfidenceIndicator confidence={confidence} size="small" />
                        <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{label}</span>
                        <span style={{ color: 'var(--text-secondary)' }}>— {description}</span>
                    </li>
                ))}
            </ul>
        </div>
    )
}

function CoreValuesStrip({ values, synthesised }: { values: string[]; synthesised: boolean }) {
    return (
        <div
            style={{
                padding: '8px 14px',
                background: 'var(--bg-surface-3)',
                borderRadius: '6px',
                fontSize: '0.75rem',
                color: 'var(--text-secondary)',
                textAlign: 'center',
            }}
        >
            <span
                style={{
                    fontSize: '0.75rem',
                    color: 'var(--text-tertiary)',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    marginRight: '8px',
                }}
            >
                Live our values:
            </span>
            {values.join(' · ')}
            {synthesised ? (
                <span style={{ marginLeft: '8px' }}>
                    <ProvenanceMarker kind="inferred" />
                </span>
            ) : null}
        </div>
    )
}
