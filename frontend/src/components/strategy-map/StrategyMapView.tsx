'use client'

import type { CSSProperties } from 'react'

import ProvenanceMarker from '@/components/analysis/ProvenanceMarker'
import type { Opportunity, StrategyMap } from '@/lib/types/api'

import StrategyMapHeader from './StrategyMapHeader'
import StrategyMapTable from './StrategyMapTable'

interface StrategyMapViewProps {
    strategyMap: StrategyMap
    /** Full opportunities array — threaded through to the table so each
     *  objective cell can render an ``OpportunityDotStrip`` keyed on
     *  ``linked_opportunity_indices``. The strip resolves each index to
     *  the linked opportunity's ``value_lever`` for dot colour. */
    opportunities: Opportunity[]
}

/**
 * AI-generated Balanced Scorecard strategy map.
 *
 * Phase 6 of ``redesign-analysis-visuals`` (design D3) replaced the
 * React-Flow free-form canvas with a CSS-grid table. Phase 12 trimmed
 * the header further (Diagnostic Tool Feedback #4). The composition
 * is now:
 *
 *   1. ``StrategyMapHeader`` — Mission banner + Vision eyebrow only.
 *      Value Proposition + Strategic Priorities relocated to
 *      ``StrategyMapDetailsSection`` (rendered separately below the
 *      table by ``AnalysisDetail``, not by this component).
 *   2. ``StrategyMapTable``  — 4 perspective rows × N theme columns,
 *      objectives stacked in each cell with the shared
 *      ``OpportunityDotStrip``. No confidence dots (dropped in P2).
 *   3. **Values strip**     — bottom strip listing the company's
 *      core values. The strip is unchanged from the old layout
 *      apart from sitting outside the (gone) canvas.
 *
 * Removed in this phase:
 *
 *   - ``StrategyMapCanvas`` (React Flow) — deleted entirely; cause-
 *     and-effect arrows that lived on the canvas are now implied by
 *     the canonical Kaplan-Norton row order in the table (Financial
 *     at top = outcome, Capacity at bottom = cause).
 *   - ``ConfidenceLegend`` — confidence dots themselves were dropped
 *     by P2 of this change; the legend explaining them is now dead.
 *
 * Print rendering uses ``PrintStrategyMapObjectives.tsx``; that path
 * was updated in this same phase for print parity.
 */
export default function StrategyMapView({ strategyMap, opportunities }: StrategyMapViewProps) {
    return (
        <section data-testid="strategy-map-view" className="strategy-map" style={sectionStyle}>
            <StrategyMapHeader strategyMap={strategyMap} />
            <StrategyMapTable strategyMap={strategyMap} opportunities={opportunities} />
            <CoreValuesStrip
                values={strategyMap.coreValues.values}
                synthesised={strategyMap.coreValues.synthesised}
            />
        </section>
    )
}

/**
 * Bottom strip listing the company's stated (or synthesised) values.
 * Unchanged from the previous layout — it just lives outside the
 * (gone) React-Flow canvas now. Centered, muted, single line; values
 * separated by a centered middot.
 */
function CoreValuesStrip({ values, synthesised }: { values: string[]; synthesised: boolean }) {
    if (values.length === 0) return null
    return (
        <div data-testid="strategy-map-core-values-strip" style={coreValuesStripStyle}>
            <span style={coreValuesLabelStyle}>Live our values:</span>
            {values.join(' · ')}
            {synthesised ? (
                <span style={{ marginLeft: '8px' }}>
                    <ProvenanceMarker kind="inferred" />
                </span>
            ) : null}
        </div>
    )
}

// ── styles ─────────────────────────────────────────────────────────

const sectionStyle: CSSProperties = {
    marginBottom: '24px',
    padding: '20px',
    background: 'var(--bg-surface)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
}

const coreValuesStripStyle: CSSProperties = {
    padding: '8px 14px',
    background: 'var(--bg-surface-3)',
    borderRadius: '6px',
    fontSize: '0.75rem',
    color: 'var(--text-secondary)',
    textAlign: 'center',
}

const coreValuesLabelStyle: CSSProperties = {
    fontSize: '0.75rem',
    color: 'var(--text-tertiary)',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    marginRight: '8px',
}
