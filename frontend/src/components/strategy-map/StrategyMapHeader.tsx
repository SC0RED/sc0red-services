'use client'

import type { CSSProperties } from 'react'

import ProvenanceMarker from '@/components/analysis/ProvenanceMarker'
import type { StrategyMap } from '@/lib/types/api'

/**
 * Header band rendered above the Balanced Scorecard table.
 *
 * Phase 12 of ``redesign-analysis-visuals`` trimmed the header to
 * Mission + Vision only per Diagnostic Tool Feedback #4 ("at the top
 * here I would just have mission and vision"). Value Proposition and
 * Strategic Priorities used to live here too but were relocated to a
 * separate collapsed ``<ExpandableSection>`` below the table — see
 * ``StrategyMapDetailsSection`` for the new home and the
 * ``strategy-map-balanced-scorecard-layout`` capability spec for the
 * placement rule.
 *
 * Current shape:
 *
 *   1. **Mission banner** — full-width prominent header card at the
 *      top of the section. Mission is the company's "why" and the
 *      first thing a PE reader should see in the strategic frame.
 *   2. **Vision eyebrow** — italic single line directly under the
 *      banner, prefixed with a small "VISION" label. The full text
 *      is exposed via the native ``title`` attribute on overflow.
 *
 * Both elements are always-visible. The previous accordion pattern
 * was dropped in P6 because reviewers consistently left the sections
 * closed and never saw the content.
 */
export default function StrategyMapHeader({ strategyMap }: { strategyMap: StrategyMap }) {
    const { vision, mission } = strategyMap

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
                the section. */}
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
        </header>
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
