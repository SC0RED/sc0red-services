'use client'

import { useEffect, useRef } from 'react'

/**
 * Shortcuts help modal — Tier 1 §5. Triggered by `?` (Shift+/).
 *
 * Renders a flat list of every shortcut grouped by category. The list
 * is the source of truth for the help dialog only; the actual key
 * handlers live in `useGlobalShortcuts`. If a shortcut is added or
 * removed there, mirror it here.
 */
const SHORTCUT_GROUPS: Array<{ heading: string; items: Array<{ keys: string[]; label: string }> }> = [
    {
        heading: 'Search',
        items: [
            { keys: ['⌘', 'K'], label: 'Open command palette' },
            { keys: ['/'], label: 'Focus search (on Analyses)' },
        ],
    },
    {
        heading: 'Navigation',
        items: [
            { keys: ['g', 'd'], label: 'Go to Dashboard' },
            { keys: ['g', 'a'], label: 'Go to Analyses' },
            { keys: ['g', 's'], label: 'Go to New Scan' },
            { keys: ['g', 't'], label: 'Go to Team' },
            { keys: ['g', 'c'], label: 'Go to Settings' },
            { keys: ['g', 'i'], label: 'Go to Connect' },
        ],
    },
    {
        heading: 'Modal',
        items: [
            { keys: ['?'], label: 'Show this help' },
            { keys: ['Esc'], label: 'Close any modal' },
        ],
    },
]

export function KeyboardShortcutsModal({
    open,
    onOpenChange,
}: {
    open: boolean
    onOpenChange: (open: boolean) => void
}) {
    const dialogRef = useRef<HTMLDivElement>(null)
    const previouslyFocusedRef = useRef<Element | null>(null)

    // Trap focus inside the dialog while open and restore focus on close.
    useEffect(() => {
        if (!open) return
        previouslyFocusedRef.current = document.activeElement
        // Focus the close button so keyboard users can tab/return immediately.
        const focusTarget = dialogRef.current?.querySelector<HTMLButtonElement>(
            'button[aria-label="Close shortcuts help"]'
        )
        focusTarget?.focus()
        return () => {
            const previous = previouslyFocusedRef.current
            if (previous instanceof HTMLElement) {
                previous.focus()
            }
        }
    }, [open])

    if (!open) return null

    return (
        <div
            className="cmdk-backdrop"
            role="dialog"
            aria-modal="true"
            aria-labelledby="shortcuts-modal-title"
            onClick={(event) => {
                if (event.target === event.currentTarget) onOpenChange(false)
            }}
        >
            <div
                ref={dialogRef}
                className="shortcuts-modal"
                onKeyDown={(event) => {
                    if (event.key === 'Escape') {
                        event.stopPropagation()
                        onOpenChange(false)
                    }
                }}
            >
                <div className="shortcuts-modal-header">
                    <h2 id="shortcuts-modal-title" className="shortcuts-modal-title">
                        Keyboard shortcuts
                    </h2>
                    <button
                        type="button"
                        aria-label="Close shortcuts help"
                        onClick={() => onOpenChange(false)}
                        className="toast-close"
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
                            <line x1="18" y1="6" x2="6" y2="18" />
                            <line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                    </button>
                </div>
                <div className="shortcuts-modal-body">
                    {SHORTCUT_GROUPS.map((group) => (
                        <section key={group.heading} className="shortcuts-group">
                            <h3 className="shortcuts-group-heading">{group.heading}</h3>
                            <dl className="shortcuts-list">
                                {group.items.map((item) => (
                                    <div key={item.label} className="shortcuts-row">
                                        <dt className="shortcuts-keys">
                                            {item.keys.map((key) => (
                                                <kbd key={key} className="shortcuts-kbd">
                                                    {key}
                                                </kbd>
                                            ))}
                                        </dt>
                                        <dd className="shortcuts-label">{item.label}</dd>
                                    </div>
                                ))}
                            </dl>
                        </section>
                    ))}
                </div>
            </div>
        </div>
    )
}
