'use client'

import type { CSSProperties, FocusEvent } from 'react'

import AnalysisLegend from '@/components/analysis/AnalysisLegend'
import OpportunityDotStrip from '@/components/analysis/OpportunityDotStrip'
import SourceLinkedOpportunitiesPopover from '@/components/analysis/SourceLinkedOpportunitiesPopover'
import { useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import type { Opportunity, StrategyMap } from '@/lib/types/api'
import {
    PERSPECTIVE_ROW_LABELS,
    PERSPECTIVE_ROW_ORDER,
    buildStrategyMapLayout,
    firstSentence,
    type StrategyMapCell,
    type StrategyMapCellObjective,
} from '@/lib/utils/strategyMapLayout'

interface StrategyMapTableProps {
    strategyMap: StrategyMap
    /** Full opportunities array — the shared ``OpportunityDotStrip``
     *  uses it to colour each dot from the linked opportunity's
     *  ``value_lever``. */
    opportunities: Opportunity[]
}

/**
 * Balanced Scorecard table renderer for the AI-generated strategy map.
 *
 * Phase 6 of ``redesign-analysis-visuals`` replaced the previous React-
 * Flow free-form canvas with this CSS-grid table layout (decision D3 in
 * ``openspec/changes/redesign-analysis-visuals/design.md``). The table
 * reads top-to-bottom in the canonical Kaplan-Norton order — Financial
 * (outcome) → Customer → Internal Processes → Organizational Capacity
 * (cause) — so the cause-and-effect chain is implied by row order
 * rather than by drawn arrows.
 *
 * Each row carries a left-side label (perspective name + fixed prose
 * subtitle from ``PERSPECTIVE_ROW_LABELS``) and a cell per theme
 * column. Cells render their objectives stacked vertically:
 *
 *   - Bold title
 *   - First sentence of the definition, muted, 2-line truncated
 *   - ``OpportunityDotStrip`` when the objective carries
 *     ``linked_opportunity_indices``
 *
 * Empty cells render placeholder boxes with the same border styling
 * so the grid alignment stays clean across all four perspectives.
 *
 * Responsive: at viewports < 900 px the table stacks vertically (each
 * perspective becomes its own section block, theme columns wrap to a
 * two-up grid) via the ``strategy-map-table--narrow`` class wired in
 * ``globals.css``. The wide breakpoint is the default render — see
 * media query in the same stylesheet for the narrow override.
 */
export default function StrategyMapTable({ strategyMap, opportunities }: StrategyMapTableProps) {
    const layout = buildStrategyMapLayout(strategyMap)
    const { themeNames, cells } = layout

    // Show the shared opportunity-link legend only when at least one
    // cell would actually render a dot — i.e. some objective has an
    // in-range linked_opportunity_indices entry. Mirrors the gating
    // ValueChainDiagram + EbitdaSection use.
    const showLegend = cells.some((row) =>
        row.some((cell) =>
            cell.objectives.some(({ objective }) =>
                (objective.linked_opportunity_indices ?? []).some(
                    (index) => index >= 0 && index < opportunities.length
                )
            )
        )
    )

    return (
        <div data-testid="strategy-map-table" style={tableStyle}>
            {showLegend && <AnalysisLegend tool="strategy-map" />}

            {/* Theme column-header row sits above the Financial row.
                The empty corner cell aligns with the perspective-label
                column on the left. */}
            <div
                style={{
                    ...gridStyle(themeNames.length),
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    color: 'var(--text-tertiary)',
                }}
            >
                <div /> {/* empty corner cell */}
                {themeNames.map((name, themeIndex) => (
                    <div
                        key={themeIndex}
                        data-testid={`strategy-map-theme-header-${themeIndex}`}
                        style={themeHeaderStyle}
                    >
                        {name}
                    </div>
                ))}
            </div>

            {/* Four perspective rows. */}
            {PERSPECTIVE_ROW_ORDER.map((perspective, perspectiveIndex) => (
                <div
                    key={perspective}
                    data-testid={`strategy-map-row-${perspective}`}
                    style={gridStyle(themeNames.length)}
                >
                    <PerspectiveLabel perspective={perspective} />
                    {cells[perspectiveIndex].map((cell, themeIndex) => (
                        <ObjectiveCell key={themeIndex} cell={cell} opportunities={opportunities} />
                    ))}
                </div>
            ))}
        </div>
    )
}

function PerspectiveLabel({ perspective }: { perspective: (typeof PERSPECTIVE_ROW_ORDER)[number] }) {
    const { title, subtitle } = PERSPECTIVE_ROW_LABELS[perspective]
    return (
        <div style={perspectiveLabelStyle}>
            <div style={perspectiveTitleStyle}>{title}</div>
            <div style={perspectiveSubtitleStyle}>{subtitle}</div>
        </div>
    )
}

function ObjectiveCell({ cell, opportunities }: { cell: StrategyMapCell; opportunities: Opportunity[] }) {
    if (cell.objectives.length === 0) {
        return (
            <div
                data-testid={`strategy-map-cell-${cell.perspective}-${cell.themeIndex}-empty`}
                style={emptyCellStyle}
            />
        )
    }
    return (
        <div data-testid={`strategy-map-cell-${cell.perspective}-${cell.themeIndex}`} style={cellStyle}>
            {cell.objectives.map((entry, index) => (
                <ObjectiveEntry
                    key={objectiveKey(entry, index)}
                    entry={entry}
                    opportunities={opportunities}
                />
            ))}
        </div>
    )
}

function ObjectiveEntry({
    entry,
    opportunities,
}: {
    entry: StrategyMapCellObjective
    opportunities: Opportunity[]
}) {
    const objective = entry.objective
    const definitionPreview = firstSentence(objective.definition)
    const linkedIndices = objective.linked_opportunity_indices ?? []
    const { highlightOpportunities, clearHighlight } = useOpportunityHover()

    // Skip dispatching when this objective has no linked indices — the
    // provider treats every dispatch as authoritative ("replaces" the
    // previous highlight), so hovering an unlinked objective would
    // silently clear whatever the previous hover source had highlighted.
    // Returning early keeps the table inert for objectives whose AI
    // synthesis left the field empty.
    const hasLinks = linkedIndices.length > 0

    const handleEnter = () => {
        if (hasLinks) highlightOpportunities(linkedIndices)
    }

    // ``onBlur`` fires when focus moves to ANY descendant of the article
    // (e.g. a future inline button inside the cell). Without the
    // relatedTarget containment check we'd clear the highlight as soon
    // as keyboard focus entered a child. Mirrors the
    // ``HoverableOpportunityCard`` + EBITDA leaf guard pattern.
    const handleBlur = (event: FocusEvent<HTMLElement>) => {
        if (event.currentTarget.contains(event.relatedTarget as Node | null)) return
        clearHighlight()
    }

    // Phase 13: wrap the source in ``SourceLinkedOpportunitiesPopover``
    // so hovering / focusing surfaces an inline popover listing the
    // linked opportunity titles. The wrapper carries the testid +
    // tabIndex + hover handlers; the inner ``<article>`` is purely
    // visual content (no event handlers, no focusable surface). This
    // keeps a single hover surface — the wrapper — so the popover's
    // open/close timers and the cross-section pulse dispatch stay in
    // sync. Sources with empty linked-indices render the wrapper but
    // the popover short-circuits internally (no popover surface).
    return (
        <SourceLinkedOpportunitiesPopover
            anchorId={`objective-${objective.id}`}
            linkedIndices={linkedIndices}
            opportunities={opportunities}
            sourceProps={{
                tabIndex: 0,
                'data-testid': `strategy-map-objective-${objective.id}`,
                onMouseEnter: handleEnter,
                onMouseLeave: clearHighlight,
                onFocus: handleEnter,
                onBlur: handleBlur,
                style: objectiveStyle,
            }}
        >
            <div style={objectiveTitleStyle}>{objective.title}</div>
            <div style={objectiveDefinitionStyle} title={objective.definition}>
                {definitionPreview}
            </div>
            <OpportunityDotStrip
                linkedIndices={linkedIndices}
                opportunities={opportunities}
                testId={`strategy-map-linked-opportunity-dots-${objective.id}`}
            />
        </SourceLinkedOpportunitiesPopover>
    )
}

/** Stable React key per cell objective. ``id`` is unique across F/C/I
 *  objectives by schema; capacity has the fixed P/T/C subkind. Index
 *  fallback handles any duplicate-id pathological case loudly via
 *  React's dev-mode warning rather than silently rendering wrong. */
function objectiveKey(entry: StrategyMapCellObjective, index: number): string {
    if (entry.kind === 'capacity') return `capacity-${entry.subkind}`
    if ('id' in entry.objective) return entry.objective.id
    return `entry-${index}`
}

// ── Styles ──────────────────────────────────────────────────────────

const tableStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
}

function gridStyle(themeCount: number): CSSProperties {
    // Left column for the perspective label is a fixed 160 px so the
    // four perspective subtitles align visually. Theme columns share
    // the remaining width evenly via ``1fr`` units.
    return {
        display: 'grid',
        gridTemplateColumns: `160px repeat(${Math.max(themeCount, 1)}, 1fr)`,
        gap: '6px',
        alignItems: 'stretch',
    }
}

const themeHeaderStyle: CSSProperties = {
    padding: '8px 10px',
}

const perspectiveLabelStyle: CSSProperties = {
    padding: '10px 12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    borderRight: '1px solid var(--border-subtle)',
}

const perspectiveTitleStyle: CSSProperties = {
    fontSize: '0.875rem',
    fontWeight: 700,
    color: 'var(--text-primary)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
}

const perspectiveSubtitleStyle: CSSProperties = {
    fontSize: '0.75rem',
    color: 'var(--text-tertiary)',
    lineHeight: 1.4,
}

const cellStyle: CSSProperties = {
    padding: '8px',
    background: 'var(--bg-surface-2)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '8px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    minHeight: '80px',
}

const emptyCellStyle: CSSProperties = {
    padding: '8px',
    border: '1px dashed var(--border-subtle)',
    borderRadius: '8px',
    minHeight: '80px',
    background: 'transparent',
}

const objectiveStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    padding: '4px 6px',
}

const objectiveTitleStyle: CSSProperties = {
    fontSize: '0.875rem',
    fontWeight: 700,
    color: 'var(--text-primary)',
    lineHeight: 1.3,
}

const objectiveDefinitionStyle: CSSProperties = {
    fontSize: '0.75rem',
    color: 'var(--text-secondary)',
    lineHeight: 1.5,
    // Truncate to 2 lines with ellipsis. The full ``definition`` is
    // exposed via the native ``title`` attribute on the parent article
    // so a hover reveals the rest.
    display: '-webkit-box',
    WebkitLineClamp: 2,
    WebkitBoxOrient: 'vertical',
    overflow: 'hidden',
}
