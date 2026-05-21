'use client'

import type { CSSProperties, ReactNode } from 'react'

import ExpandableCard from '@/components/ui/ExpandableCard'
import type { StrategicPriority, ValuePropositionClassification } from '@/lib/types/api'
import { formatValueProposition } from '@/lib/utils/strategyMapUtils'

interface StrategyMapDetailsSectionProps {
    valueProposition: ValuePropositionClassification
    strategicPriorities: StrategicPriority[]
}

/**
 * Collapsed-by-default section carrying Value Proposition + Strategic
 * Priorities. Phase 12 of ``redesign-analysis-visuals`` relocated this
 * content out of the strategy-map header (per Diagnostic Tool Feedback
 * #4 — "at the top here I would just have mission and vision") and into
 * a separate ``<ExpandableCard>`` that sits between the BSC table and
 * the next page section.
 *
 * Trigger label format:
 *
 *   "Value Proposition & Strategic Priorities · N"   (when both present;
 *                                                     N = priority count)
 *   "Value Proposition"                               (when only VP present)
 *   "Strategic Priorities · N"                        (when only priorities present)
 *
 * The parent (``AnalysisDetail``) is responsible for gating the
 * mount on ``hasStrategyDetails = valueProposition.primary ||
 * strategicPriorities.length > 0``; this component trusts its props
 * and renders both blocks unconditionally. Per CLAUDE.md fail-fast,
 * a defensive in-component null-return on empty input was removed —
 * the call-site gate is the single source of truth.
 *
 * See ``strategy-map-balanced-scorecard-layout`` spec requirement
 * "Value Proposition and Strategic Priorities render in a collapsed
 * section below the table" for the full contract.
 */
export default function StrategyMapDetailsSection({
    valueProposition,
    strategicPriorities,
}: StrategyMapDetailsSectionProps) {
    const hasValueProp = Boolean(valueProposition.primary)
    const hasPriorities = strategicPriorities.length > 0

    const valueLabel = formatValueProposition(valueProposition.primary, valueProposition.secondary)

    const triggerLabel = computeTriggerLabel(hasValueProp, hasPriorities, strategicPriorities.length)

    return (
        <ExpandableCard
            id="strategy-map-details"
            header={
                <span data-testid="strategy-map-details-trigger" style={triggerLabelStyle}>
                    {triggerLabel}
                </span>
            }
        >
            <div data-testid="strategy-map-details-body" style={bodyStyle}>
                {hasValueProp ? (
                    <section data-testid="strategy-map-value-proposition" style={blockStyle}>
                        <div style={eyebrowStyle}>Value Proposition</div>
                        <LabelledItem name={valueLabel}>{valueProposition.rationale}</LabelledItem>
                    </section>
                ) : null}

                {hasValueProp && hasPriorities ? <hr style={dividerStyle} /> : null}

                {hasPriorities ? (
                    <section data-testid="strategy-map-strategic-priorities" style={blockStyle}>
                        <div style={eyebrowStyle}>Strategic Priorities</div>
                        <ol style={priorityListStyle}>
                            {strategicPriorities.map((priority, index) => (
                                <li key={priority.name} style={priorityItemStyle}>
                                    <span style={priorityIndexStyle}>{index + 1}</span>
                                    <LabelledItem name={priority.name}>{priority.result}</LabelledItem>
                                </li>
                            ))}
                        </ol>
                    </section>
                ) : null}
            </div>
        </ExpandableCard>
    )
}

/**
 * Build the trigger label from which sections will render. Pure
 * helper, exported via test-id targeting only — callers don't need
 * to touch this directly.
 */
function computeTriggerLabel(hasValueProp: boolean, hasPriorities: boolean, priorityCount: number): string {
    if (hasValueProp && hasPriorities) {
        return `Value Proposition & Strategic Priorities · ${priorityCount}`
    }
    if (hasValueProp) {
        return 'Value Proposition'
    }
    return `Strategic Priorities · ${priorityCount}`
}

/**
 * Shared block layout for "highlighted identity claim" rows — blue
 * accent left border + uppercase heading + paragraph detail. Same
 * treatment that used to live inside ``StrategyMapHeader`` before
 * Phase 12 trimmed the header.
 */
function LabelledItem({ name, children }: { name: string; children: ReactNode }) {
    return (
        <div style={labelledItemStyle}>
            <h4 style={labelledItemHeadingStyle}>{name}</h4>
            <p style={bodyParagraphStyle}>{children}</p>
        </div>
    )
}

// ── styles ─────────────────────────────────────────────────────────

const triggerLabelStyle: CSSProperties = {
    fontSize: '0.875rem',
    fontWeight: 600,
    color: 'var(--text-primary)',
}

const bodyStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    padding: '14px 18px 18px',
}

const blockStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
}

const eyebrowStyle: CSSProperties = {
    fontSize: '0.75rem',
    color: 'var(--text-tertiary)',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
}

const dividerStyle: CSSProperties = {
    border: 0,
    borderTop: '1px solid var(--border-subtle)',
    margin: 0,
}

const priorityListStyle: CSSProperties = {
    listStyle: 'none',
    padding: 0,
    margin: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
}

const priorityItemStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '12px',
}

const priorityIndexStyle: CSSProperties = {
    flex: '0 0 auto',
    width: '24px',
    height: '24px',
    borderRadius: '50%',
    background: 'var(--accent-blue-glow)',
    color: 'var(--accent-blue)',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '0.75rem',
    fontWeight: 700,
    marginTop: '2px',
}

const labelledItemStyle: CSSProperties = {
    paddingLeft: '12px',
    borderLeft: '3px solid var(--accent-blue)',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    flex: 1,
    minWidth: 0,
}

const labelledItemHeadingStyle: CSSProperties = {
    margin: 0,
    fontSize: '0.875rem',
    fontWeight: 700,
    color: 'var(--text-primary)',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
}

const bodyParagraphStyle: CSSProperties = {
    margin: 0,
    fontSize: '0.875rem',
    color: 'var(--text-secondary)',
    lineHeight: 1.6,
}
