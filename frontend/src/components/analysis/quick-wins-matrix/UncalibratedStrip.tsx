'use client'

import type { CSSProperties } from 'react'

import { useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import type { Opportunity } from '@/lib/types/api'
import { LEVER_COLORS } from '@/lib/utils/leverColors'

/**
 * Footer strip rendered below the scatter plot, showing opportunities
 * with either numeric axis missing. Same hover/click semantics as the
 * in-plot dots — paper readers and matrix users get a uniform way to
 * highlight + jump to the matching opportunity card regardless of
 * whether the AI was able to size it.
 *
 * Renders ``null`` when there are no uncalibrated entries; the wrapper
 * component just inlines this without a wrapping gate.
 */
export default function UncalibratedStrip({
    indices,
    opportunities,
}: {
    indices: number[]
    opportunities: Opportunity[]
}) {
    // Hook calls must run unconditionally — early-return AFTER the hook
    // to satisfy the Rules of Hooks. The empty-render fallback is a
    // no-op visually but keeps the hook order stable across renders.
    const { highlightOpportunities, clearHighlight } = useOpportunityHover()
    if (indices.length === 0) return null

    return (
        <div data-testid="quick-wins-uncalibrated-strip" style={uncalibratedContainerStyle}>
            <div style={uncalibratedLabelStyle}>Opportunities without ROI / investment estimates</div>
            <div style={uncalibratedDotsStyle}>
                {indices.map((opportunityIndex) => {
                    const opportunity = opportunities[opportunityIndex]
                    if (!opportunity) {
                        throw new Error(
                            `QuickWinsMatrix uncalibrated strip: opportunity index ${opportunityIndex} out of range`
                        )
                    }
                    const lever = opportunity.value_lever ?? 'Both'
                    const color = LEVER_COLORS[lever] ?? 'var(--text-tertiary)'
                    const onActivate = () => highlightOpportunities([opportunityIndex])
                    const onClick = () => {
                        highlightOpportunities([opportunityIndex])
                        const target = document.querySelector(
                            `[data-testid="opportunity-card-${opportunityIndex}"]`
                        )
                        target?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
                    }
                    return (
                        <button
                            key={opportunityIndex}
                            type="button"
                            data-testid={`quick-wins-uncalibrated-dot-${opportunityIndex}`}
                            aria-label={`Highlight opportunity: ${opportunity.title}`}
                            title={`${opportunity.title} (${lever})`}
                            onMouseEnter={onActivate}
                            onMouseLeave={clearHighlight}
                            onFocus={onActivate}
                            onBlur={clearHighlight}
                            onClick={onClick}
                            style={{ ...uncalibratedDotStyle, background: color }}
                        />
                    )
                })}
            </div>
        </div>
    )
}

// ── styles ────────────────────────────────────────────────────────

const uncalibratedContainerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    padding: '10px 14px',
    background: 'var(--bg-surface-2)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '6px',
}

const uncalibratedLabelStyle: CSSProperties = {
    fontSize: '0.75rem',
    color: 'var(--text-tertiary)',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
}

const uncalibratedDotsStyle: CSSProperties = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '6px',
}

const uncalibratedDotStyle: CSSProperties = {
    width: '12px',
    height: '12px',
    borderRadius: '50%',
    border: '1px solid var(--bg-surface)',
    padding: 0,
    cursor: 'pointer',
}
