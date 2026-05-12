'use client'

import { useId, useState, type ReactNode } from 'react'

interface ExpandableCardProps {
    /**
     * Identifies this card instance. Combined with an internal
     * `useId()` prefix to ensure the resulting DOM id is unique even
     * if multiple ExpandableCards on the page share the same `id`
     * value. The string is sanitised internally — spaces and any
     * characters outside the HTML5 id-token grammar are replaced
     * with `-` so callers can safely pass arbitrary strings (e.g.
     * an opportunity title like `"Deploy AI Chatbot"`) without
     * breaking the resulting `aria-controls` IDREFS parsing.
     */
    id: string
    /** Header content rendered inside the trigger `<button>`. */
    header: ReactNode
    /** Body content revealed when expanded. */
    children: ReactNode
    /**
     * Controlled-mode flag. When provided alongside `onToggle`,
     * the parent owns the open state — typical pattern for
     * single-open accordion across siblings (parent tracks "which
     * id is open" and passes `isOpen={parentState === id}`).
     *
     * When omitted, the component manages its own open/closed
     * state via `useState(false)` — uncontrolled mode for callers
     * that don't need accordion coordination.
     */
    isOpen?: boolean
    /**
     * Controlled-mode toggle handler. Called whenever the user
     * clicks the trigger. Receives no arguments — the parent
     * computes the next open state based on its own model.
     */
    onToggle?: () => void
    /**
     * Optional className applied to the wrapping `.card` element
     * for caller-specific extras. The base classes (`card`,
     * `card--list`, `expandable-card`) and `overflow: hidden` are
     * already applied internally.
     */
    className?: string
}

/**
 * Click-to-reveal-detail card primitive. One chevron position
 * (top-right of the header row), one glyph (▼ rotating to ▲ on
 * open via CSS transform), one motion duration. Wraps content in
 * the `.card.card--list` density variant so visual padding and
 * surface treatment are consistent across every expandable
 * surface on the analysis-detail page.
 *
 * Replaces hand-rolled button/card patterns in `RiskBreakdown` and
 * `OpportunitiesList` per UX Audit 2. `ValueChainDiagram` and
 * `WhatsMissingPanel` are explicitly deferred — the former because
 * its horizontal Porter's-value-chain visual is fundamentally
 * different from a list of cards, the latter because its
 * accent-strip aesthetic intentionally diverges from the
 * `.card.card--list` glassmorphism surface. Both wait on follow-up
 * proposals that handle their visual model separately.
 *
 * The body always renders in the DOM (with the `hidden` HTML
 * attribute when closed, NOT conditional rendering) so the
 * trigger's `aria-controls` always references a valid element.
 * `hidden` is the standardised way to hide content from both
 * sighted users and screen readers without removing it from the
 * DOM tree.
 *
 * Strategy-map header's `<details>/<summary>` accordion is
 * intentionally NOT migrated — it uses a different primitive
 * (native browser disclosure element controlled by parent state).
 * Chevron-glyph alignment between the two primitives is a separate
 * CSS-only follow-up.
 */
export default function ExpandableCard({
    id,
    header,
    children,
    isOpen: controlledIsOpen,
    onToggle,
    className,
}: ExpandableCardProps) {
    // Controlled if `isOpen` was passed (even as `false`); uncontrolled if undefined.
    const isControlled = controlledIsOpen !== undefined
    const [uncontrolledOpen, setUncontrolledOpen] = useState(false)
    const isOpen = isControlled ? controlledIsOpen : uncontrolledOpen

    // Stable DOM id for aria-controls + body element. `useId` ensures
    // uniqueness across React-tree instances even when the caller's
    // `id` prop collides with another caller's.
    //
    // Sanitise the caller's `id` — strip whitespace and any character
    // outside the HTML5 id-token grammar. Critical for `aria-controls`,
    // which is parsed as a SPACE-DELIMITED LIST of ID references by
    // assistive technologies. A caller passing an opportunity title
    // like `"Deploy AI Chatbot"` would otherwise produce an
    // `aria-controls` value that NVDA/JAWS/VoiceOver split into 3
    // separate IDREFs, none of which exist — silently breaking the
    // accordion relationship for screen-reader users.
    const reactId = useId()
    const safeId = id.replace(/\s+/g, '-').replace(/[^a-zA-Z0-9\-_:.]/g, '')
    const bodyId = `expandable-card-body-${reactId}-${safeId}`

    const handleClick = () => {
        if (isControlled) {
            onToggle?.()
        } else {
            setUncontrolledOpen((prev) => !prev)
        }
    }

    return (
        <div
            className={`card card--list expandable-card${className ? ` ${className}` : ''}`}
            style={{ overflow: 'hidden' }}
        >
            <button
                type="button"
                className="expandable-card__trigger"
                aria-expanded={isOpen}
                aria-controls={bodyId}
                onClick={handleClick}
            >
                <span className="expandable-card__header">{header}</span>
                <ChevronGlyph isOpen={isOpen} />
            </button>
            <div id={bodyId} className="expandable-card__body" hidden={!isOpen}>
                {children}
            </div>
        </div>
    )
}

/**
 * Down-chevron SVG that rotates 180° via CSS when `isOpen`. The
 * `data-open` attribute is the rotation hook — keeping the
 * transform in CSS lets `prefers-reduced-motion` collapse it
 * automatically via the global stylesheet rule.
 */
function ChevronGlyph({ isOpen }: { isOpen: boolean }) {
    return (
        <svg
            className="expandable-card__chevron"
            data-open={isOpen}
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
        >
            <polyline points="6 9 12 15 18 9" />
        </svg>
    )
}
