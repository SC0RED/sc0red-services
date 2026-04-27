'use client'

import { useEffect, useId, useRef, useState } from 'react'

import { HELP_CONTENT, type HelpTerm } from '@/lib/help-content'

interface HelpTooltipProps {
    /** Key into the `HELP_CONTENT` registry. */
    term: HelpTerm
    /** Override the icon's accessible label. Default: `What is {title}?`. */
    label?: string
}

/**
 * ⓘ icon that reveals a small popover with a short PE-domain explainer.
 *
 * Triggers (matches conventional inline-help patterns):
 *   - **Hover** on desktop (pointer enter/leave)
 *   - **Focus** for keyboard users (Tab onto the icon → popover opens)
 *   - **Click / tap** opens the popover; it is dismissed via blur,
 *     pointer-leave (no focus inside), Escape, or an outside click.
 *     The click handler is intentionally idempotent (always opens)
 *     rather than a toggle — toggling produced flicker on touch
 *     devices that fire pointerEnter before the click event.
 *   - **Escape** closes when open
 *   - **Click outside** also closes (touch-friendly dismiss)
 *
 * A11y: the popover stays mounted in the DOM at all times — toggled
 * visible/hidden via a `data-state` attribute and CSS — so a screen
 * reader that begins announcing the description on focus does not get
 * cut off by a mid-announcement unmount when the user Tabs away. The
 * trigger advertises the popover via `aria-describedby` so the
 * description is announced on focus regardless of visual state (which
 * is exactly what we want for an inline help affordance — keyboard
 * users always hear the help). `aria-hidden` on the popover mirrors
 * `!open` so screen readers don't double-read it while the user is
 * browsing the DOM with the tooltip "closed".
 *
 * Animation honours the global `prefers-reduced-motion: reduce` rule in
 * `globals.css` (collapses animation-duration → popover appears instantly).
 *
 * Content lives in `frontend/src/lib/help-content.ts` — see the doc comment
 * there for editing rules. Mirror at `docs/help-content.md` for review.
 */
export default function HelpTooltip({ term, label }: HelpTooltipProps) {
    const entry = HELP_CONTENT[term]
    const [open, setOpen] = useState(false)
    const tooltipId = useId()
    const containerRef = useRef<HTMLSpanElement>(null)

    useEffect(() => {
        if (!open) return
        const handleKey = (event: KeyboardEvent) => {
            if (event.key === 'Escape') setOpen(false)
        }
        const handlePointer = (event: PointerEvent) => {
            // Click-outside dismiss. Use pointerdown so it fires before
            // any click handler on the page can act on the same gesture.
            if (!containerRef.current) return
            if (!containerRef.current.contains(event.target as Node)) {
                setOpen(false)
            }
        }
        document.addEventListener('keydown', handleKey)
        document.addEventListener('pointerdown', handlePointer)
        return () => {
            document.removeEventListener('keydown', handleKey)
            document.removeEventListener('pointerdown', handlePointer)
        }
    }, [open])

    const accessibleLabel = label ?? `What is ${entry.title}?`

    function handlePointerLeave() {
        // Don't close on pointer-leave if focus is still inside the trigger
        // — a keyboard user who tabbed onto the icon shouldn't lose the
        // popover when their mouse incidentally passes through.
        if (containerRef.current?.contains(document.activeElement)) return
        setOpen(false)
    }

    return (
        <span
            ref={containerRef}
            className="help-tooltip"
            onPointerEnter={() => setOpen(true)}
            onPointerLeave={handlePointerLeave}
        >
            <button
                type="button"
                aria-label={accessibleLabel}
                aria-describedby={tooltipId}
                aria-expanded={open}
                onClick={() => setOpen(true)}
                onFocus={() => setOpen(true)}
                onBlur={() => setOpen(false)}
                className="help-tooltip-trigger"
            >
                <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                >
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="16" x2="12" y2="12" />
                    <line x1="12" y1="8" x2="12.01" y2="8" />
                </svg>
            </button>
            <span
                role="tooltip"
                id={tooltipId}
                className="help-tooltip-popover"
                data-state={open ? 'open' : 'closed'}
                aria-hidden={!open}
            >
                <span className="help-tooltip-title">{entry.title}</span>
                <span className="help-tooltip-body">{entry.body}</span>
            </span>
        </span>
    )
}
