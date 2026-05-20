'use client'

import { type ReactNode } from 'react'

import { useOpportunityHover } from '@/lib/hooks/useOpportunityHover'

/**
 * Wraps each opportunity card with the P5 hover-provider integration.
 *
 * - SOURCE: hovering / focusing the card calls
 *   ``highlightOpportunities([originalIndex])`` so sources elsewhere
 *   (EBITDA leaves, value-chain steps, strategy-map cells, Quick Wins
 *   matrix chips) that reference this opportunity can react to the
 *   reverse-direction lookup.
 * - TARGET: when the provider's ``hoveredOpportunityIndices`` includes
 *   this card's ``originalIndex``, the wrapper applies the
 *   ``.card-pulse`` class — a one-shot 400 ms outline glow.
 *
 * **Hovering does NOT scroll the page.** The original P5 design fired
 * ``scrollIntoView({ block: 'nearest' })`` on every transition into
 * the highlight state. In production review (post-P1b) PE readers
 * complained that hovering a strategy-map cell pulled the page
 * out from under them — they were trying to LOOK at the cell, not
 * navigate. Scroll-on-hover was removed; intentional navigation
 * (e.g. clicking a Quick Wins matrix chip) handles scroll
 * imperatively at the click site instead.
 *
 * Stateless about its own pulse: the class is toggled by re-running
 * the component each time ``isHovered`` flips. Re-applying the class
 * restarts the animation because browsers reset CSS animations when
 * a class carrying an ``animation`` shorthand is removed and re-added
 * to the same element. React's reconciler keeps the DOM node stable
 * (no remount) — the animation restart is a browser-level side-effect
 * of the class toggle, not a React lifecycle event.
 */
export default function HoverableOpportunityCard({
    originalIndex,
    children,
}: {
    originalIndex: number
    children: ReactNode
}) {
    const { hoveredOpportunityIndices, highlightOpportunities, clearHighlight } = useOpportunityHover()
    const isHovered = hoveredOpportunityIndices.includes(originalIndex)

    // ``onBlur`` bubbles up from any focusable descendant — including
    // the ``<button>`` inside ``ExpandableCard``. A naive
    // ``onBlur={clearHighlight}`` would fire when keyboard focus
    // moves FROM the wrapper INTO the expand button, clearing the
    // highlight that ``onFocus`` had just set. Guard against bubbling
    // by checking whether focus moved to a descendant.
    function handleBlur(event: React.FocusEvent<HTMLDivElement>) {
        const next = event.relatedTarget as Node | null
        if (event.currentTarget.contains(next)) return
        clearHighlight()
    }

    return (
        <div
            data-testid={`opportunity-card-${originalIndex}`}
            className={isHovered ? 'card-pulse' : undefined}
            onMouseEnter={() => highlightOpportunities([originalIndex])}
            onMouseLeave={clearHighlight}
            onFocus={() => highlightOpportunities([originalIndex])}
            onBlur={handleBlur}
        >
            {children}
        </div>
    )
}
