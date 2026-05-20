'use client'

import type { CSSProperties, ReactNode } from 'react'

import ProvenanceMarker from '@/components/analysis/ProvenanceMarker'
import type { StrategyMap } from '@/lib/types/api'
import { formatValueProposition } from '@/lib/utils/strategyMapUtils'

/**
 * Header band rendered above the Balanced Scorecard table.
 *
 * Phase 6 of ``redesign-analysis-visuals`` (design D3) replaced the
 * previous click-to-expand accordion with a flat, always-visible
 * banner stack:
 *
 *   1. **Mission banner** — full-width prominent header card at the
 *      top of the section. Mission is the company's "why" and the
 *      first thing a PE reader should see in the strategic frame.
 *   2. **Vision eyebrow** — italic single line directly under the
 *      banner, prefixed with a small "VISION" label. The full text
 *      is exposed via the native ``title`` attribute on overflow.
 *   3. **Value Proposition** — left-bar block underneath, showing
 *      the value-prop classification label + rationale. Always
 *      open (no toggle).
 *   4. **Strategic Priorities** — same left-bar treatment, one
 *      block per priority, listing the priority name + result.
 *
 * The accordion pattern was removed because reviewers consistently
 * left the sections closed and never saw the content. With the
 * table-style scorecard below, vertical real-estate is no longer
 * the constraint it was under the React-Flow canvas — everything
 * fits inline.
 */
export default function StrategyMapHeader({ strategyMap }: { strategyMap: StrategyMap }) {
    const { vision, mission, valueProposition, strategicPriorities } = strategyMap
    const valueLabel = formatValueProposition(valueProposition.primary, valueProposition.secondary)

    return (
        <header
            data-testid="strategy-map-header"
            style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '14px',
                paddingBottom: '12px',
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

            {/* Mission banner — the prominent "why" card at the top of
                the section. Replaces the previous click-to-expand
                disclosure so the statement is always in view. */}
            <section data-testid="strategy-map-mission-banner" style={missionBannerStyle}>
                <div style={missionLabelStyle}>
                    Mission
                    {mission.synthesised ? (
                        <span style={{ marginLeft: '8px' }}>
                            <ProvenanceMarker kind="inferred" />
                        </span>
                    ) : null}
                </div>
                <p style={missionStatementStyle}>{mission.statement}</p>
            </section>

            {/* Vision eyebrow — single italic line under the banner.
                Truncated with ellipsis; native ``title`` exposes the
                full text on overflow hover. */}
            <div style={visionRowStyle}>
                <span style={visionEyebrowLabelStyle}>Vision</span>
                <p title={vision.statement} data-testid="strategy-map-vision" style={visionStatementStyle}>
                    &ldquo;{vision.statement}&rdquo;
                    {vision.synthesised ? (
                        <span style={{ marginLeft: '8px', fontStyle: 'normal' }}>
                            <ProvenanceMarker kind="inferred" />
                        </span>
                    ) : null}
                </p>
            </div>

            {/* Value Proposition — always-visible left-bar block. */}
            <SectionGroup label="Value Proposition" testId="strategy-map-value-proposition">
                <LabelledItem name={valueLabel}>{valueProposition.rationale}</LabelledItem>
            </SectionGroup>

            {/* Strategic Priorities — one left-bar block per priority. */}
            {strategicPriorities.length > 0 ? (
                <SectionGroup label="Strategic Priorities" testId="strategy-map-strategic-priorities">
                    <ul style={priorityListStyle}>
                        {strategicPriorities.map((priority) => (
                            <li key={priority.name}>
                                <LabelledItem name={priority.name}>{priority.result}</LabelledItem>
                            </li>
                        ))}
                    </ul>
                </SectionGroup>
            ) : null}
        </header>
    )
}

/**
 * Small uppercase label + body wrapper. Replaces the previous
 * ``ExpandableSection`` shell — the body always renders.
 */
function SectionGroup({ label, testId, children }: { label: string; testId: string; children: ReactNode }) {
    return (
        <section data-testid={testId} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={sectionGroupLabelStyle}>{label}</div>
            {children}
        </section>
    )
}

/**
 * Shared block layout for any "highlighted identity claim" in the
 * header — the value-proposition classification + each strategic
 * priority. Blue accent left border + uppercase heading + paragraph
 * detail underneath.
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

const missionBannerStyle: CSSProperties = {
    padding: '14px 18px',
    background: 'var(--bg-surface-2)',
    border: '1px solid var(--border-subtle)',
    borderLeft: '4px solid var(--accent-blue)',
    borderRadius: '8px',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
}

const missionLabelStyle: CSSProperties = {
    fontSize: '0.75rem',
    color: 'var(--accent-blue)',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    display: 'flex',
    alignItems: 'center',
}

const missionStatementStyle: CSSProperties = {
    margin: 0,
    fontSize: '1rem',
    color: 'var(--text-primary)',
    lineHeight: 1.5,
    fontWeight: 600,
}

const visionRowStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'baseline',
    gap: '10px',
    minWidth: 0,
}

const visionEyebrowLabelStyle: CSSProperties = {
    fontSize: '0.75rem',
    color: 'var(--text-tertiary)',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    flex: '0 0 auto',
}

const visionStatementStyle: CSSProperties = {
    margin: 0,
    fontSize: '0.875rem',
    fontStyle: 'italic',
    color: 'var(--text-primary)',
    lineHeight: 1.4,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    minWidth: 0,
    flex: 1,
}

const sectionGroupLabelStyle: CSSProperties = {
    fontSize: '0.75rem',
    color: 'var(--text-tertiary)',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
}

const priorityListStyle: CSSProperties = {
    listStyle: 'none',
    padding: 0,
    margin: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
}

const bodyParagraphStyle: CSSProperties = {
    margin: 0,
    fontSize: '0.875rem',
    color: 'var(--text-secondary)',
    lineHeight: 1.6,
}

const labelledItemStyle: CSSProperties = {
    paddingLeft: '12px',
    borderLeft: '3px solid var(--accent-blue)',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
}

const labelledItemHeadingStyle: CSSProperties = {
    margin: 0,
    fontSize: '0.875rem',
    fontWeight: 700,
    color: 'var(--text-primary)',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
}
