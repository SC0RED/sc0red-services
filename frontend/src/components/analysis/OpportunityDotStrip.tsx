import type { CSSProperties } from 'react'

import type { Opportunity } from '@/lib/types/api'
import { LEVER_COLORS } from '@/lib/utils/leverColors'

interface OpportunityDotStripProps {
    /** Index pointers into the analysis's `opportunities` array. The shape
     *  matches `ValueChainStep.opportunity_indices`,
     *  `EbitdaNode.linked_opportunity_indices`, and the new
     *  `BalancedScorecardObjective.linked_opportunity_indices` field
     *  added by P1a of the `redesign-analysis-visuals` change. Empty or
     *  undefined renders nothing. */
    linkedIndices: number[] | undefined
    /** Full opportunities list — same array the analysis page hands to the
     *  rest of the analysis sections. Indexed by `linkedIndices`. */
    opportunities: Opportunity[]
    /** Maximum number of dots to render inline before collapsing the rest
     *  into a `+N` overflow badge. Defaults to 5. The badge is announced
     *  in the accessible name so screen readers know there are more. */
    maxVisible?: number
    /** Optional `data-testid` for callers that want to scope their
     *  assertions (e.g. the EBITDA chip's existing
     *  `ebitda-linked-opportunity-dots` testid for backward compat). */
    testId?: string
}

/**
 * Shared "this node has linked opportunities" overlay used by every
 * analysis tool with index pointers into the opportunities array.
 *
 * Visual: a row of small (8 px) circular dots. Each dot's colour comes
 * from `LEVER_COLORS` keyed off the linked opportunity's `value_lever`
 * — Revenue Side green, Cost Side violet, Both cyan, missing/unknown
 * defaults to `--text-secondary`. The lever colour is the
 * decision-relevant signal for a PE reader; the individual opportunity
 * titles are surfaced via the native `title` tooltip on each dot.
 *
 * Lifted from the inline implementation in `EbitdaNodeComponent`
 * (introduced by PR #305) into a shared component as part of P2-4 of
 * the `redesign-analysis-visuals` change. The three analysis tools
 * (strategy map, EBITDA tree, value chain) now share one visual
 * vocabulary for "X targets this".
 *
 * Accessibility: each dot is `aria-hidden` (purely decorative — the
 * colour is the signal). The strip itself has an `aria-label`
 * summarising the count so screen readers announce "3 opportunities
 * target this" instead of three separate "decorative" announcements.
 *
 * Overflow: when there are more linked opportunities than `maxVisible`,
 * the first `maxVisible - 1` dots render plus a `+N` overflow badge
 * (also focusable, with the overflow titles in its `title` attribute
 * — keeps the at-a-glance scan honest without blowing up the chip
 * height).
 */
export default function OpportunityDotStrip({
    linkedIndices,
    opportunities,
    maxVisible = 5,
    testId,
}: OpportunityDotStripProps) {
    // `linkedIndices ?? []` rather than a `!== undefined` guard so the
    // empty-array case and the undefined case render the same: nothing.
    // This matches the API contract — see `FinancialObjective`'s
    // `linked_opportunity_indices` doc comment.
    const indices = linkedIndices ?? []
    if (indices.length === 0) {
        return null
    }

    // Resolve indices to opportunities. Out-of-range indices (stale data
    // from a re-analysis where the opportunities array shrank) are
    // silently dropped — the strip just renders fewer dots. Surfacing a
    // visible "missing opportunity" placeholder would be louder than
    // the bug deserves; the next reanalyze cycle reconciles it.
    const linked = indices
        .map((index) => opportunities[index])
        .filter((opportunity): opportunity is Opportunity => Boolean(opportunity))

    if (linked.length === 0) {
        return null
    }

    // Overflow rule: when ``linked.length > maxVisible``, the strip
    // shows ``maxVisible - 1`` dots followed by a ``+N`` badge that
    // takes the maxVisible-th slot (so the row still caps at maxVisible
    // visual elements). The badge's count is the number of opportunities
    // genuinely hidden behind it — i.e. everything past the visible
    // slice, NOT ``linked.length - maxVisible``.
    const willOverflow = linked.length > maxVisible
    const visibleCount = willOverflow ? maxVisible - 1 : linked.length
    const visible = linked.slice(0, visibleCount)
    const hidden = linked.slice(visibleCount)
    const overflowCount = hidden.length

    const accessibleSummary =
        linked.length === 1 ? '1 opportunity targets this' : `${linked.length} opportunities target this`

    return (
        <div data-testid={testId} aria-label={accessibleSummary} role="img" style={stripStyle}>
            {visible.map((opportunity, position) => (
                <span
                    key={position}
                    aria-hidden="true"
                    title={`${opportunity.title}${
                        opportunity.value_lever ? ` (${opportunity.value_lever})` : ''
                    }`}
                    style={{
                        ...dotStyle,
                        background:
                            (opportunity.value_lever && LEVER_COLORS[opportunity.value_lever]) ||
                            'var(--text-secondary)',
                    }}
                />
            ))}
            {overflowCount > 0 && (
                <span
                    aria-hidden="true"
                    // The overflow badge is keyboard-focusable so callers
                    // that wrap the strip in a hover provider can pick
                    // up focus events without per-dot wiring. The native
                    // `title` carries the hidden opportunity titles so a
                    // mouse-hover scan stays honest about what's behind
                    // the badge.
                    tabIndex={0}
                    title={hidden.map((opportunity) => opportunity.title).join('\n')}
                    style={overflowBadgeStyle}
                >
                    +{overflowCount}
                </span>
            )}
        </div>
    )
}

const stripStyle: CSSProperties = {
    display: 'flex',
    gap: '4px',
    flexWrap: 'wrap',
    alignItems: 'center',
}

const dotStyle: CSSProperties = {
    display: 'inline-block',
    width: '8px',
    height: '8px',
    borderRadius: '50%',
}

const overflowBadgeStyle: CSSProperties = {
    fontSize: '0.625rem',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    padding: '0 4px',
    borderRadius: '6px',
    background: 'var(--bg-surface-3)',
    cursor: 'help',
    lineHeight: '14px',
    minWidth: '20px',
    textAlign: 'center',
}
