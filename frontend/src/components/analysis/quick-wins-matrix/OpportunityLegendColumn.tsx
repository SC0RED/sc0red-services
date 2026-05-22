'use client'

import { useCallback, type CSSProperties } from 'react'

import { useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import type { Opportunity } from '@/lib/types/api'
import { LEVER_COLORS } from '@/lib/utils/leverColors'
import {
    QUADRANT_LABELS,
    type Quadrant,
    type buildQuickWinsMatrixLayout,
} from '@/lib/utils/quickWinsMatrixLayout'

/**
 * Sidebar legend rendered next to the ROI × Investment scatter plot.
 *
 * Each plotted opportunity is identified on-chart by a numbered badge
 * (``#N``); this column maps ``#N`` → full opportunity title, grouped
 * by quadrant in the same order the chart reads (Quick Wins → Strategic
 * Bets → Fill-Ins → Deprioritise). Cluster pins collapse into a single
 * "X opportunities in this quadrant" entry that still expands the dot
 * numbers inline so the user can resolve any badge on the chart without
 * opening the cluster popover.
 *
 * The column also gives the chart a non-scrolling way to enumerate
 * every opportunity for keyboard-only users, who previously had to tab
 * through the dots one at a time.
 *
 * Hover / focus an entry → ``useOpportunityHover`` pulses the matching
 * dot on the chart AND the matching opportunity card below.
 * Click an entry → scroll the opportunity card into view (same
 * behaviour as clicking the dot itself).
 *
 * Uncalibrated opportunities (no ROI or no investment) appear in a
 * separate "Uncalibrated" group at the bottom of the column — the
 * matching footer strip below the chart still renders the dots, but
 * the legend gives them a numbered identity that lines up with the
 * dot order in the strip.
 */
/** Top → bottom-right reading order matching the chart's quadrant
 *  geometry, so the legend reads in the same direction a user scans
 *  the plot. Hoisted to module scope — it's a literal constant and
 *  would otherwise rebuild on every render. */
const QUADRANT_READING_ORDER: Quadrant[] = ['quick-wins', 'strategic-bets', 'fill-ins', 'deprioritise']

export default function OpportunityLegendColumn({
    layout,
    opportunities,
}: {
    layout: ReturnType<typeof buildQuickWinsMatrixLayout>
    opportunities: Opportunity[]
}) {
    // Build a map quadrant → ordered list of opportunity indices it
    // contains. Cluster pins flatten into the same list so the legend
    // is a complete enumeration regardless of whether a quadrant
    // collapsed.
    const indicesByQuadrant: Record<Quadrant, number[]> = {
        'quick-wins': [],
        'strategic-bets': [],
        'fill-ins': [],
        deprioritise: [],
    }
    for (const dot of layout.inPlot) {
        indicesByQuadrant[dot.quadrant].push(dot.opportunityIndex)
    }
    for (const pin of layout.clusterPins) {
        for (const opportunityIndex of pin.opportunityIndices) {
            indicesByQuadrant[pin.quadrant].push(opportunityIndex)
        }
    }

    const uncalibratedIndices = layout.uncalibrated.map((entry) => entry.opportunityIndex)

    const hasAnyEntries =
        QUADRANT_READING_ORDER.some((quadrant) => indicesByQuadrant[quadrant].length > 0) ||
        uncalibratedIndices.length > 0

    return (
        <aside
            data-testid="quick-wins-legend-column"
            aria-label="Opportunity legend for the ROI by Investment matrix"
            style={columnStyle}
        >
            {hasAnyEntries ? null : (
                <p data-testid="quick-wins-legend-empty" style={emptyStateStyle}>
                    No opportunities to plot yet.
                </p>
            )}
            {QUADRANT_READING_ORDER.map((quadrant) => {
                const indices = indicesByQuadrant[quadrant]
                if (indices.length === 0) return null
                return (
                    <LegendGroup
                        key={quadrant}
                        title={QUADRANT_LABELS[quadrant]}
                        testId={`quick-wins-legend-group-${quadrant}`}
                        opportunityIndices={indices}
                        opportunities={opportunities}
                    />
                )
            })}
            {uncalibratedIndices.length > 0 ? (
                <LegendGroup
                    title="Uncalibrated"
                    titleSuffix="ROI or investment not estimated"
                    testId="quick-wins-legend-group-uncalibrated"
                    opportunityIndices={uncalibratedIndices}
                    opportunities={opportunities}
                />
            ) : null}
        </aside>
    )
}

// ── Internal components ───────────────────────────────────────────

function LegendGroup({
    title,
    titleSuffix,
    testId,
    opportunityIndices,
    opportunities,
}: {
    title: string
    titleSuffix?: string
    testId: string
    opportunityIndices: number[]
    opportunities: Opportunity[]
}) {
    return (
        <section data-testid={testId} style={groupStyle}>
            <h4 style={groupHeadingStyle}>
                {title}
                {titleSuffix ? <span style={groupHeadingSuffixStyle}>{` · ${titleSuffix}`}</span> : null}
            </h4>
            <ul style={groupListStyle}>
                {opportunityIndices.map((opportunityIndex) => (
                    <LegendEntry
                        key={opportunityIndex}
                        opportunityIndex={opportunityIndex}
                        opportunity={opportunities[opportunityIndex]}
                    />
                ))}
            </ul>
        </section>
    )
}

function LegendEntry({
    opportunityIndex,
    opportunity,
}: {
    opportunityIndex: number
    opportunity: Opportunity | undefined
}) {
    const { highlightOpportunities, clearHighlight, hoveredOpportunityIndices } = useOpportunityHover()

    const onActivate = useCallback(() => {
        highlightOpportunities([opportunityIndex])
    }, [highlightOpportunities, opportunityIndex])

    const onClick = useCallback(() => {
        highlightOpportunities([opportunityIndex])
        const target = document.querySelector(`[data-testid="opportunity-card-${opportunityIndex}"]`)
        target?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }, [highlightOpportunities, opportunityIndex])

    if (!opportunity) {
        // Per CLAUDE.md fail-fast: a missing opportunity for an index
        // the layout produced is a bug, not a user-visible state. The
        // layout helper emits indices in lock-step with the
        // ``opportunities`` array it was given, so an out-of-range
        // index here means the caller passed a stale array — flag it
        // loudly rather than silently dropping the entry.
        throw new Error(
            `OpportunityLegendColumn: opportunity index ${opportunityIndex} out of range ` +
                'in legend rendering — caller likely passed a stale opportunities array to the layout helper.'
        )
    }

    const lever = opportunity.value_lever ?? 'Both'
    const color = LEVER_COLORS[lever] ?? 'var(--text-tertiary)'
    const isActive = hoveredOpportunityIndices.includes(opportunityIndex)
    const number = opportunityIndex + 1

    return (
        <li>
            <button
                type="button"
                data-testid={`quick-wins-legend-entry-${opportunityIndex}`}
                aria-label={`Highlight opportunity ${number}: ${opportunity.title}`}
                onMouseEnter={onActivate}
                onMouseLeave={clearHighlight}
                onFocus={onActivate}
                onBlur={clearHighlight}
                onClick={onClick}
                style={{
                    ...entryButtonStyle,
                    background: isActive ? 'var(--bg-surface-3)' : 'transparent',
                }}
            >
                <span
                    aria-hidden="true"
                    style={{
                        ...entryNumberStyle,
                        // Donut treatment matches the matrix
                        // ``ScatterDot``: lever-coloured ring + neutral
                        // interior + lever-coloured number. The 3 px
                        // inset ring scales the matrix dot's 4 px ring
                        // (24 px outer) down to this badge's 20 px
                        // outer while keeping the ring/interior ratio.
                        boxShadow: `inset 0 0 0 3px ${color}`,
                        color,
                    }}
                >
                    {number}
                </span>
                <span style={entryTitleStyle}>{opportunity.title}</span>
            </button>
        </li>
    )
}

// ── styles ────────────────────────────────────────────────────────

const columnStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '14px',
    minWidth: 0,
}

const emptyStateStyle: CSSProperties = {
    margin: 0,
    fontSize: '0.875rem',
    color: 'var(--text-tertiary)',
    fontStyle: 'italic',
}

const groupStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    minWidth: 0,
}

const groupHeadingStyle: CSSProperties = {
    margin: 0,
    fontSize: '0.75rem',
    color: 'var(--text-tertiary)',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
}

const groupHeadingSuffixStyle: CSSProperties = {
    fontWeight: 400,
    textTransform: 'none',
    letterSpacing: '0.02em',
    color: 'var(--text-tertiary)',
}

const groupListStyle: CSSProperties = {
    listStyle: 'none',
    margin: 0,
    padding: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
}

const entryButtonStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    width: '100%',
    textAlign: 'left',
    border: 'none',
    padding: '6px 8px',
    borderRadius: '4px',
    fontSize: '0.875rem',
    color: 'var(--text-primary)',
    cursor: 'pointer',
    transition: 'background 80ms linear',
    minWidth: 0,
}

const entryNumberStyle: CSSProperties = {
    flex: '0 0 auto',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '20px',
    height: '20px',
    borderRadius: '50%',
    background: 'var(--bg-surface-3)',
    fontSize: '0.75rem',
    fontWeight: 700,
    lineHeight: 1,
    // ``color`` + ``boxShadow`` (ring) applied per-entry inline so
    // they pick up the per-opportunity lever colour.
}

const entryTitleStyle: CSSProperties = {
    flex: '1 1 auto',
    minWidth: 0,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    lineHeight: 1.4,
}
