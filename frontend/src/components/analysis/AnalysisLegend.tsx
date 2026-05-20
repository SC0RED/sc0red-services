import type { CSSProperties } from 'react'

import { LEVER_COLORS } from '@/lib/utils/leverColors'

interface AnalysisLegendProps {
    /** Which analysis tool this legend sits above — selects the noun
     *  the legend's sentence uses to describe what the dots target. */
    tool: 'strategy-map' | 'ebitda' | 'value-chain'
    /** Optional `data-testid` override. Defaults to a stable per-tool
     *  testid so callers can assert legend presence without rebinding
     *  the value at every call site. */
    testId?: string
}

const TOOL_NOUN: Record<AnalysisLegendProps['tool'], string> = {
    'strategy-map': 'objective',
    ebitda: 'P&L line',
    'value-chain': 'value-chain step',
}

const TOOL_TESTID_DEFAULT: Record<AnalysisLegendProps['tool'], string> = {
    'strategy-map': 'strategy-map-opportunity-link-legend',
    ebitda: 'ebitda-opportunity-link-legend',
    'value-chain': 'value-chain-opportunity-link-legend',
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
 * Renders only when a caller has at least one node carrying linked
 * opportunities — i.e. the parent component is expected to gate the
 * `<AnalysisLegend />` mount on a `treeHasLinkedOpportunities`-style
 * predicate. This keeps legacy analyses (no `linked_opportunity_indices`
 * data anywhere) from rendering an explanation for dots that aren't on
 * the page.
 *
 * Introduced by P2 of the `redesign-analysis-visuals` change. Replaces
 * the inline EBITDA legend that PR #305 added.
 */
export default function AnalysisLegend({ tool, testId }: AnalysisLegendProps) {
    const noun = TOOL_NOUN[tool]
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
            <span>{` — AI opportunities targeting this ${noun}.`}</span>
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
