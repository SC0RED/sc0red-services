'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Hover-intent state with safe-transit grace period.
 *
 * Why this exists: when a tooltip is rendered in a portal (e.g. React
 * Flow's `<NodeToolbar>`), it lives in a separate DOM tree from the
 * trigger element. Moving the cursor from trigger → tooltip therefore
 * briefly leaves both areas (the visual gap between them sits in
 * neither), which fires `mouseLeave` on the trigger before
 * `mouseEnter` fires on the tooltip. A naive `setHovered(false)` on
 * `mouseLeave` closes the tooltip mid-transit and the user can never
 * reach it.
 *
 * This hook returns:
 *   - `hovered`: derived boolean for whether the tooltip should show.
 *   - `openNow()`: cancels any pending close + sets hovered=true.
 *     Wire to BOTH the trigger's `onMouseEnter`/`onFocus` AND the
 *     tooltip's `onMouseEnter`.
 *   - `scheduleClose()`: starts the close timer. Wire to BOTH the
 *     trigger's `onMouseLeave`/`onBlur` AND the tooltip's
 *     `onMouseLeave`.
 *   - `setHovered(value)`: imperative override — used for
 *     keyboard-activation toggles (Enter/Space on a `role="button"`
 *     trigger).
 *
 * 200 ms is the established hover-intent default — long enough to
 * cover most cursor transits, short enough that an intentional
 * "look away" reads as immediate.
 */
const DEFAULT_CLOSE_DELAY_MS = 200

export interface HoverIntent {
    hovered: boolean
    openNow: () => void
    scheduleClose: () => void
    setHovered: (value: boolean | ((current: boolean) => boolean)) => void
}

export function useHoverIntent(closeDelayMs: number = DEFAULT_CLOSE_DELAY_MS): HoverIntent {
    const [hovered, setHovered] = useState(false)
    // Pending close-timeout. Captured in a ref so handlers can cancel it
    // without re-running effects.
    const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

    const cancelClose = useCallback(() => {
        if (closeTimerRef.current !== null) {
            clearTimeout(closeTimerRef.current)
            closeTimerRef.current = null
        }
    }, [])

    const openNow = useCallback(() => {
        cancelClose()
        setHovered(true)
    }, [cancelClose])

    const scheduleClose = useCallback(() => {
        cancelClose()
        closeTimerRef.current = setTimeout(() => {
            closeTimerRef.current = null
            setHovered(false)
        }, closeDelayMs)
    }, [cancelClose, closeDelayMs])

    // Drop any pending timer if the component unmounts mid-transit so
    // we don't call setState on an unmounted component.
    useEffect(() => () => cancelClose(), [cancelClose])

    return { hovered, openNow, scheduleClose, setHovered }
}
