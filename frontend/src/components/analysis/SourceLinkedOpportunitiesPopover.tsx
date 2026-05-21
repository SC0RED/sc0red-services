'use client'

import {
    useCallback,
    useEffect,
    useId,
    useRef,
    useState,
    type CSSProperties,
    type FocusEvent,
    type KeyboardEvent,
    type ReactNode,
} from 'react'

import SourceLinkedOpportunitiesPopoverContent from '@/components/analysis/SourceLinkedOpportunitiesPopoverContent'
import type { Opportunity } from '@/lib/types/api'

/**
 * Source-side popover that lists the opportunities a strategy-map
 * cell / EBITDA leaf / value-chain step links to. Added by Phase 13
 * of ``redesign-analysis-visuals`` (design D7) to close the
 * Diagnostic Tool Feedback #5c gap — hover used to pulse the matching
 * opportunity card below, but the pulse was invisible when the card
 * lived below the fold (which it always did in production).
 *
 * The popover surfaces the same titles a user would reach by
 * scrolling, without forcing the scroll. Click an entry → imperative
 * ``scrollIntoView`` on the matching ``opportunity-card-{n}`` element
 * + ``highlightOpportunities([index])`` dispatch. (Click-side wiring
 * lives in ``SourceLinkedOpportunitiesPopoverContent``; this file
 * owns only the anchor wrapper + open/close lifecycle.)
 *
 * Lifecycle:
 *
 *   - Open after 150 ms dwell on ``mouseEnter`` (avoids flicker when
 *     the cursor is transiting past the source).
 *   - Open immediately on keyboard ``focus`` (no debounce — keyboard
 *     users have already targeted).
 *   - Close after 200 ms grace on ``mouseLeave`` (so the cursor can
 *     transit from anchor → popover without dismissal).
 *   - Close immediately on ``Escape``, outside click, or blur with
 *     ``relatedTarget`` outside the popover.
 *
 * The component does NOT wire the hover provider's pulse dispatch
 * itself — the consuming source already does that around its own
 * ``onMouseEnter`` / ``onFocus`` handlers passed in via ``sourceProps``.
 * This component is purely the popover surface; the consuming source
 * composes the hover lifecycle.
 *
 * **Test-id scheme:** see ``SourceLinkedOpportunitiesPopoverContent``.
 */

/** 150 ms dwell debounce on mouseEnter — long enough to filter out
 *  transit-past hovers, short enough that an intentional pointer-rest
 *  reads as immediate. */
const OPEN_DELAY_MS = 150

/** 200 ms grace on close — matches the existing ``useHoverIntent``
 *  default; long enough for cursor → popover transit, short enough
 *  that an intentional "look away" closes promptly. */
const CLOSE_DELAY_MS = 200

export interface SourceLinkedOpportunitiesPopoverProps {
    /** Stable identifier for this anchor (objective ID, leaf ID, step
     *  ID). Used to disambiguate test IDs across multiple popovers on
     *  the same page. */
    anchorId: string
    /** Indices into ``opportunities``. Empty array → popover never
     *  renders. Component-level short-circuit kept here (not at the
     *  call site) because every consumer needs the same behaviour and
     *  duplicating the guard would be repetitive. */
    linkedIndices: number[]
    /** Full opportunities array — titles + value-lever colours
     *  resolved per index at render. */
    opportunities: Opportunity[]
    /** Source content to wrap. The wrapper sets ``position: relative``
     *  so the popover can absolute-position against it; consumer
     *  styling on the inner element is preserved. */
    children: ReactNode
    /** Spread onto the inner wrapper. Use this so the consumer's own
     *  ``onMouseEnter`` / ``onFocus`` / ``onMouseLeave`` / ``onBlur``
     *  handlers (for the cross-section hover provider) still fire. */
    sourceProps?: {
        tabIndex?: number
        'data-testid'?: string
        'aria-label'?: string
        onMouseEnter?: () => void
        onMouseLeave?: () => void
        onFocus?: () => void
        onBlur?: (event: FocusEvent<HTMLElement>) => void
        onClick?: () => void
        style?: CSSProperties
        className?: string
    }
}

/**
 * Wraps a source surface (objective cell, EBITDA leaf, value-chain
 * step) with a floating linked-opportunities popover. The wrapper is
 * a ``<div>`` set to ``position: relative`` so the popover can
 * absolute-position against it; consumer styling on the inner
 * children stays put.
 */
export default function SourceLinkedOpportunitiesPopover({
    anchorId,
    linkedIndices,
    opportunities,
    children,
    sourceProps,
}: SourceLinkedOpportunitiesPopoverProps) {
    // Empty-linkage short-circuit — no popover surface for sources
    // that don't link anywhere. Saves consumers from gating at the
    // call site; the spec explicitly forbids rendering an empty
    // popover.
    const hasLinks = linkedIndices.length > 0

    const [isOpen, setIsOpen] = useState(false)
    const openTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const anchorWrapperRef = useRef<HTMLDivElement>(null)
    const popoverRef = useRef<HTMLDivElement>(null)

    const cancelOpen = useCallback(() => {
        if (openTimerRef.current !== null) {
            clearTimeout(openTimerRef.current)
            openTimerRef.current = null
        }
    }, [])

    const cancelClose = useCallback(() => {
        if (closeTimerRef.current !== null) {
            clearTimeout(closeTimerRef.current)
            closeTimerRef.current = null
        }
    }, [])

    const scheduleOpen = useCallback(() => {
        if (!hasLinks) return
        cancelClose()
        cancelOpen()
        openTimerRef.current = setTimeout(() => {
            openTimerRef.current = null
            setIsOpen(true)
        }, OPEN_DELAY_MS)
    }, [cancelClose, cancelOpen, hasLinks])

    const openImmediately = useCallback(() => {
        if (!hasLinks) return
        cancelOpen()
        cancelClose()
        setIsOpen(true)
    }, [cancelClose, cancelOpen, hasLinks])

    const scheduleClose = useCallback(() => {
        cancelOpen()
        cancelClose()
        closeTimerRef.current = setTimeout(() => {
            closeTimerRef.current = null
            setIsOpen(false)
        }, CLOSE_DELAY_MS)
    }, [cancelClose, cancelOpen])

    const closeImmediately = useCallback(() => {
        cancelOpen()
        cancelClose()
        setIsOpen(false)
    }, [cancelClose, cancelOpen])

    // Drop pending timers on unmount.
    useEffect(
        () => () => {
            cancelOpen()
            cancelClose()
        },
        [cancelOpen, cancelClose]
    )

    // Outside-click close. Listener only attaches while the popover
    // is open so we don't pay for a global handler on every page.
    useEffect(() => {
        if (!isOpen) return
        const onDocMouseDown = (event: MouseEvent) => {
            const target = event.target as Node | null
            if (!target) return
            if (anchorWrapperRef.current?.contains(target)) return
            if (popoverRef.current?.contains(target)) return
            closeImmediately()
        }
        document.addEventListener('mousedown', onDocMouseDown)
        return () => document.removeEventListener('mousedown', onDocMouseDown)
    }, [isOpen, closeImmediately])

    const handleAnchorMouseEnter = useCallback(() => {
        sourceProps?.onMouseEnter?.()
        scheduleOpen()
    }, [sourceProps, scheduleOpen])

    const handleAnchorMouseLeave = useCallback(() => {
        sourceProps?.onMouseLeave?.()
        scheduleClose()
    }, [sourceProps, scheduleClose])

    const handleAnchorFocus = useCallback(() => {
        sourceProps?.onFocus?.()
        openImmediately()
    }, [sourceProps, openImmediately])

    const handleAnchorBlur = useCallback(
        (event: FocusEvent<HTMLDivElement>) => {
            // Containment guard: if focus moved into the popover (or
            // any descendant), keep both the popover AND the
            // cross-section pulse lit. The popover IS the hover
            // surface while it's open, so the consumer's blur handler
            // (which clears the pulse) must NOT fire when focus is
            // simply moving INTO the popover — it should only fire
            // when focus leaves the source surface entirely.
            const nextTarget = event.relatedTarget as Node | null
            if (nextTarget && popoverRef.current?.contains(nextTarget)) {
                return
            }
            // Schedule close FIRST so the popover dismissal happens
            // in lockstep with the pulse clear. Without this order
            // the pulse would clear immediately while the popover
            // remained on-screen for the 200 ms close grace — a
            // visible transient state where the source visibly says
            // "no longer hovered" but the popover is still up.
            scheduleClose()
            sourceProps?.onBlur?.(event as unknown as FocusEvent<HTMLElement>)
        },
        [sourceProps, scheduleClose]
    )

    const handleAnchorKeyDown = useCallback(
        (event: KeyboardEvent<HTMLDivElement>) => {
            if (event.key === 'Escape' && isOpen) {
                event.preventDefault()
                closeImmediately()
            }
        },
        [isOpen, closeImmediately]
    )

    const handlePopoverMouseEnter = useCallback(() => {
        // Cursor entered popover — cancel any pending close so the
        // user can scroll / click without dismissal.
        cancelClose()
    }, [cancelClose])

    const handlePopoverMouseLeave = useCallback(() => {
        scheduleClose()
    }, [scheduleClose])

    const handlePopoverKeyDown = useCallback(
        (event: KeyboardEvent<HTMLDivElement>) => {
            if (event.key === 'Escape') {
                event.preventDefault()
                closeImmediately()
            }
        },
        [closeImmediately]
    )

    const reactId = useId()
    const popoverDomId = `source-linked-popover-${reactId}`

    // The wrapper is a ``<div>`` (not ``<span>``) so it can host block-
    // flow children like ``<article>`` without nesting block-inside-
    // inline. Consumers control the visual ``display`` via
    // ``sourceProps.style.display`` — default is block flow. The
    // wrapper itself owns ``position: relative`` so the popover can
    // absolute-position against it.
    return (
        <div
            ref={anchorWrapperRef}
            style={{ position: 'relative', ...(sourceProps?.style ?? {}) }}
            className={sourceProps?.className}
            tabIndex={sourceProps?.tabIndex}
            data-testid={sourceProps?.['data-testid']}
            aria-label={sourceProps?.['aria-label']}
            aria-describedby={isOpen ? popoverDomId : undefined}
            onMouseEnter={handleAnchorMouseEnter}
            onMouseLeave={handleAnchorMouseLeave}
            onFocus={handleAnchorFocus}
            onBlur={handleAnchorBlur}
            onKeyDown={handleAnchorKeyDown}
            onClick={sourceProps?.onClick}
        >
            {children}
            {hasLinks && isOpen ? (
                <SourceLinkedOpportunitiesPopoverContent
                    anchorId={anchorId}
                    linkedIndices={linkedIndices}
                    opportunities={opportunities}
                    popoverDomId={popoverDomId}
                    popoverRef={popoverRef}
                    onMouseEnter={handlePopoverMouseEnter}
                    onMouseLeave={handlePopoverMouseLeave}
                    onKeyDown={handlePopoverKeyDown}
                    onClose={closeImmediately}
                />
            ) : null}
        </div>
    )
}
