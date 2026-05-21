'use client'

import { useCallback } from 'react'

import { useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import type { Opportunity } from '@/lib/types/api'
import { LEVER_COLORS } from '@/lib/utils/leverColors'
import type { InPlotDot } from '@/lib/utils/quickWinsMatrixLayout'
import { truncate } from '@/lib/utils/stringUtils'

/** Max characters in the inline dot label before truncation. Keeps
 *  labels short enough not to dominate the chart but long enough to
 *  recognise the opportunity ("Deploy AI churn pred…" stays meaningful). */
const MAX_LABEL_CHARS = 22

/**
 * Individual scatter-plot dot for one opportunity.
 *
 * Renders inside the matrix's SVG plot area at the dot's pre-projected
 * (x, y) coordinates. Hover/focus pulses the matching opportunity card
 * via the shared ``useOpportunityHover`` provider; click also scrolls
 * the card into view (separate code path so hover never scrolls — see
 * the P1b regression test for the rationale).
 *
 * Each dot also renders an inline title label to its right so the
 * chart is readable without hovering. Labels truncate at
 * ``MAX_LABEL_CHARS``; the full title is still available via the
 * SVG ``<title>`` tooltip + accessibility aria-label.
 *
 * ``clampedUp`` dots render a ``↑`` caret above the dot to flag that
 * the raw ROI value exceeded the visual cap.
 */
export default function ScatterDot({ dot, opportunity }: { dot: InPlotDot; opportunity: Opportunity }) {
    const { highlightOpportunities, clearHighlight } = useOpportunityHover()
    const lever = opportunity.value_lever ?? 'Both'
    const color = LEVER_COLORS[lever] ?? 'var(--text-tertiary)'
    const truncatedTitle = truncate(opportunity.title, MAX_LABEL_CHARS)

    const onActivate = useCallback(() => {
        highlightOpportunities([dot.opportunityIndex])
    }, [highlightOpportunities, dot.opportunityIndex])

    const onClick = useCallback(() => {
        highlightOpportunities([dot.opportunityIndex])
        const target = document.querySelector(`[data-testid="opportunity-card-${dot.opportunityIndex}"]`)
        target?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }, [highlightOpportunities, dot.opportunityIndex])

    return (
        <g
            data-testid={`quick-wins-dot-${dot.opportunityIndex}`}
            tabIndex={0}
            role="button"
            aria-label={`Highlight opportunity: ${opportunity.title}`}
            transform={`translate(${dot.x}, ${dot.y})`}
            onMouseEnter={onActivate}
            onMouseLeave={clearHighlight}
            onFocus={onActivate}
            onBlur={clearHighlight}
            onClick={onClick}
            style={{ cursor: 'pointer' }}
        >
            <title>{`${opportunity.title} (${lever})`}</title>
            <circle r={5} fill={color} stroke="var(--bg-surface)" strokeWidth={1} />
            {dot.clampedUp ? (
                <text
                    x={0}
                    y={-9}
                    textAnchor="middle"
                    style={{ fontSize: '10px', fill: 'var(--text-tertiary)' }}
                    aria-hidden="true"
                >
                    ↑
                </text>
            ) : null}
            <text
                data-testid={`quick-wins-dot-label-${dot.opportunityIndex}`}
                x={9}
                y={4}
                // ``aria-hidden`` because the parent ``<g>`` already
                // announces the FULL (un-truncated) title via its
                // aria-label. Without this, screen readers would
                // announce the title twice — once full, once clipped.
                aria-hidden="true"
                style={{
                    fontSize: '11px',
                    fill: 'var(--text-secondary)',
                    pointerEvents: 'none',
                }}
            >
                {truncatedTitle}
            </text>
        </g>
    )
}
