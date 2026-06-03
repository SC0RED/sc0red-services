'use client'

import { useCallback } from 'react'

import { useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import type { Opportunity } from '@/lib/types/api'
import { LEVER_COLORS } from '@/lib/utils/leverColors'
import type { InPlotDot } from '@/lib/utils/quickWinsMatrixLayout'

/**
 * Individual scatter-plot dot for one opportunity.
 *
 * Renders inside the matrix's SVG plot area at the dot's pre-projected
 * (x, y) coordinates. Hover / focus pulses the matching opportunity
 * card via the shared ``useOpportunityHover`` provider; click also
 * scrolls the card into view (separate code path so hover never scrolls
 * — see the P1b regression test for the rationale).
 *
 * Each dot is a coloured badge bearing its 1-based opportunity number
 * (``#N``). The full title lives in the sidebar
 * ``OpportunityLegendColumn`` so the chart itself stays uncluttered —
 * inline title text (the previous design) collided whenever two dots
 * landed in the same horizontal band, which happens frequently in
 * Quick Wins because clusters are the whole point of the chart.
 *
 * ``clampedUp`` dots render a ``↑`` caret above the dot to flag that
 * the raw ROI value exceeded the visual cap.
 *
 * When the dot's opportunity is currently highlighted by the shared
 * hover provider (because the user is hovering this dot, or hovering
 * the matching card / legend entry below), a focus ring renders behind
 * the badge so the user can identify the active dot inside dense
 * clusters.
 */
export default function ScatterDot({ dot, opportunity }: { dot: InPlotDot; opportunity: Opportunity }) {
    const { highlightOpportunities, clearHighlight, hoveredOpportunityIndices } = useOpportunityHover()
    const lever = opportunity.value_lever ?? 'Both'
    const color = LEVER_COLORS[lever] ?? 'var(--text-tertiary)'
    const isActive = hoveredOpportunityIndices.includes(dot.opportunityIndex)
    // 1-based label matches what the sidebar legend prints, so a user
    // who reads "#3 — Cut SaaS sprawl" in the legend can find the dot
    // labelled "3" on the chart without an extra mental offset.
    const number = dot.opportunityIndex + 1

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
            aria-label={`Highlight opportunity ${number}: ${opportunity.title}`}
            transform={`translate(${dot.x}, ${dot.y})`}
            onMouseEnter={onActivate}
            onMouseLeave={clearHighlight}
            onFocus={onActivate}
            onBlur={clearHighlight}
            onClick={onClick}
            style={{ cursor: 'pointer' }}
        >
            <title>{`#${number} ${opportunity.title} (${lever})`}</title>
            {/* Active-state focus ring. Renders behind the badge so the
                badge's own fill remains the primary visual. Hidden when
                the dot is not in the hovered set — the simple opacity
                toggle avoids React conditional-mount churn so the SVG
                tree stays stable across hover transitions.
                ``data-active`` is the semantic signal tests assert on
                so a future swap to ``visibility``/``display`` doesn't
                break the contract. */}
            <circle
                data-testid={`quick-wins-dot-ring-${dot.opportunityIndex}`}
                data-active={isActive ? 'true' : 'false'}
                r={16}
                fill="none"
                stroke={color}
                strokeWidth={2}
                opacity={isActive ? 0.55 : 0}
            />
            <circle data-testid={`quick-wins-dot-outer-${dot.opportunityIndex}`} r={12} fill={color} />
            <circle
                data-testid={`quick-wins-dot-inner-${dot.opportunityIndex}`}
                r={8}
                fill="var(--bg-surface-3)"
            />
            <text
                data-testid={`quick-wins-dot-number-${dot.opportunityIndex}`}
                textAnchor="middle"
                dy={3}
                aria-hidden="true"
                style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    fill: color,
                    pointerEvents: 'none',
                }}
            >
                {number}
            </text>
            {dot.clampedUp ? (
                <text
                    x={0}
                    y={-14}
                    textAnchor="middle"
                    style={{ fontSize: '10px', fill: 'var(--text-tertiary)' }}
                    aria-hidden="true"
                >
                    ↑
                </text>
            ) : null}
        </g>
    )
}
