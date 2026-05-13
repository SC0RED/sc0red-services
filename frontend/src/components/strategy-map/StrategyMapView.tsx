'use client'

import ProvenanceMarker from '@/components/analysis/ProvenanceMarker'
import type { StrategyMap } from '@/lib/types/api'

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
 *   3. `CoreValuesStrip`         — bottom strip listing the company's
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
            <CoreValuesStrip
                values={strategyMap.coreValues.values}
                synthesised={strategyMap.coreValues.synthesised}
            />
        </section>
    )
}

function CoreValuesStrip({ values, synthesised }: { values: string[]; synthesised: boolean }) {
    return (
        <div
            style={{
                padding: '8px 14px',
                background: 'var(--bg-surface-3)',
                borderRadius: '6px',
                fontSize: '0.8rem',
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
