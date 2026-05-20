'use client'

import { useEffect, useRef, type ReactNode } from 'react'

import { useOpportunityHover } from '@/lib/hooks/useOpportunityHover'

/**
 * Wraps each opportunity card with the P5 hover-provider integration.
 *
 * - SOURCE: hovering / focusing the card calls
 *   ``highlightOpportunities([originalIndex])`` so sources elsewhere
 *   (EBITDA leaves, value-chain steps) that reference this opportunity
 *   can react to the reverse-direction lookup.
 * - TARGET: when the provider's ``hoveredOpportunityIndices`` includes
 *   this card's ``originalIndex``, the wrapper applies the
 *   ``.card-pulse`` class (one-shot 400 ms outline glow) and calls
 *   ``scrollIntoView({ block: 'nearest' })`` so the card lands in the
 *   viewport if it was scrolled offscreen. ``nearest`` means we only
 *   scroll when the card is fully out of view — already-visible cards
 *   stay put.
 *
 * Stateless about its own pulse: the class is toggled by re-running
 * the component each time ``isHovered`` flips. Re-applying the class
 * restarts the animation because browsers reset CSS animations when
 * a class carrying an ``animation`` shorthand is removed and re-added
 * to the same element. React's reconciler keeps the DOM node stable
 * (no remount) — the animation restart is a browser-level side-effect
 * of the class toggle, not a React lifecycle event.
 *
 * Lifted out of ``OpportunitiesList.tsx`` to keep that file under the
 * 360-line per-component frontend limit (CLAUDE.md). The wrapper is
 * the only consumer today, but a future analyses-page card grid (or
 * the print path that wants to render the same highlight state) could
 * reuse it without re-extracting.
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
    const wasHovered = useRef(false)
    const wrapperRef = useRef<HTMLDivElement>(null)

    // On transition INTO highlight state, scroll the card into view.
    // ``block: 'nearest'`` means already-visible cards don't move;
    // only offscreen cards scroll. We compare against the previous
    // ``isHovered`` (via ref) so we don't re-scroll on every render
    // while the card stays hovered.
    useEffect(() => {
        if (isHovered && !wasHovered.current) {
            wrapperRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
        }
        wasHovered.current = isHovered
    }, [isHovered])

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
            ref={wrapperRef}
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
