import type { CSSProperties } from 'react'

import { LEVER_COLORS } from '@/lib/utils/leverColors'

interface AnalysisLegendProps {
    /** Which analysis tool this legend sits above — selects the noun
     *  the legend's sentence uses to describe what the dots target.
     *  ``quick-wins-matrix`` is a special case: on the matrix the dot
     *  IS the opportunity (not something that "targets" one), so the
     *  trailing copy changes from "targeting this X" to "coloured by
     *  value lever". */
    tool: 'strategy-map' | 'ebitda' | 'value-chain' | 'quick-wins-matrix'
    /** Optional `data-testid` override. Defaults to a stable per-tool
     *  testid so callers can assert legend presence without rebinding
     *  the value at every call site. */
    testId?: string
}

/** Trailing sentence rendered after the three swatches. Each tool gets
 *  its own copy because the noun the legend "targets" varies, and the
 *  matrix in particular flips the relationship (the dot IS the
 *  opportunity, it doesn't target one). Centralised here so the screen
 *  + print + accessibility surfaces all read the same way. */
const TOOL_LEGEND_COPY: Record<AnalysisLegendProps['tool'], string> = {
    'strategy-map': ' — AI opportunities targeting this objective.',
    ebitda: ' — AI opportunities targeting this P&L line.',
    'value-chain': ' — AI opportunities targeting this value-chain step.',
    'quick-wins-matrix': ' — each dot is an AI opportunity, coloured by value lever.',
}

const TOOL_TESTID_DEFAULT: Record<AnalysisLegendProps['tool'], string> = {
    'strategy-map': 'strategy-map-opportunity-link-legend',
    ebitda: 'ebitda-opportunity-link-legend',
    'value-chain': 'value-chain-opportunity-link-legend',
    'quick-wins-matrix': 'quick-wins-matrix-lever-legend',
}

/**
 * One-line legend that sits above each analysis tool's canvas/table
 * explaining the opportunity-link dot colours used by
 * `OpportunityDotStrip`.
 *
 * The legend reads:
 *
 *   ● Revenue Side · ● Cost Side · ● Both — AI opportunities targeting this <noun>
 *
 * where `<noun>` is "objective" for strategy map, "P&L line" for
 * EBITDA, and "value-chain step" for value chain.
 *
 * Sources its dot swatches from the SAME `LEVER_COLORS` map the
 * `OpportunityDotStrip` dots use, so the legend and the dots cannot
 * drift on colour by construction.
 *
 * Gating differs by tool:
 *
 * - `strategy-map`, `ebitda`, `value-chain` — the parent component is
 *   expected to gate the `<AnalysisLegend />` mount on a
 *   `treeHasLinkedOpportunities`-style predicate. This keeps legacy
 *   analyses (no `linked_opportunity_indices` data anywhere) from
 *   rendering an explanation for dots that aren't on the page.
 * - `quick-wins-matrix` — mounted unconditionally by the matrix wrapper.
 *   The matrix dots ARE the opportunities (not links to nodes), so there
 *   is no "no linked opportunities anywhere" case and no predicate to
 *   gate on.
 *
 * Introduced by P2 of the `redesign-analysis-visuals` change. Replaces
 * the inline EBITDA legend that PR #305 added.
 */
export default function AnalysisLegend({ tool, testId }: AnalysisLegendProps) {
    const effectiveTestId = testId ?? TOOL_TESTID_DEFAULT[tool]

    return (
        <div data-testid={effectiveTestId} style={legendStyle}>
            <Swatch lever="Revenue Side" />
            <strong>Revenue Side</strong>
            <span aria-hidden="true"> · </span>
            <Swatch lever="Cost Side" />
            <strong>Cost Side</strong>
            <span aria-hidden="true"> · </span>
            <Swatch lever="Both" />
            <strong>Both</strong>
            <span>{TOOL_LEGEND_COPY[tool]}</span>
        </div>
    )
}

function Swatch({ lever }: { lever: 'Revenue Side' | 'Cost Side' | 'Both' }) {
    return (
        <span
            aria-hidden="true"
            style={{
                ...swatchStyle,
                background: LEVER_COLORS[lever],
            }}
        />
    )
}

const legendStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    fontSize: '0.75rem',
    color: 'var(--text-secondary)',
    lineHeight: 1.5,
    flexWrap: 'wrap',
    marginBottom: '8px',
}

const swatchStyle: CSSProperties = {
    display: 'inline-block',
    width: '8px',
    height: '8px',
    borderRadius: '50%',
}
