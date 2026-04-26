'use client'

import { usePathname, useRouter } from 'next/navigation'
import { useCallback, useEffect, useRef, useState } from 'react'

import { CommandPalette } from '@/components/ui/CommandPalette'
import { KeyboardShortcutsModal } from '@/components/ui/KeyboardShortcutsModal'

/**
 * Global keyboard shortcut handler — Tier 1 §5.
 *
 * Mounted once inside the authenticated layout. Owns:
 *   - Cmd-K (or Ctrl-K) → open command palette
 *   - `?`               → open shortcuts help modal
 *   - `g d`/`g a`/`g s`/`g t`/`g c` chord → navigate
 *   - `/`               → focus search input on /analyses
 *   - `Esc`             → close topmost modal (palette > shortcuts)
 *
 * Shortcuts are suppressed when the user is typing in any input,
 * textarea, or contenteditable element. The `g`-prefix chord uses a
 * 1-second window before resetting.
 */
const CHORD_TIMEOUT_MS = 1000

const NAV_CHORDS: Record<string, string> = {
    d: '/dashboard',
    a: '/analyses',
    s: '/scan/new',
    t: '/team',
    c: '/settings',
}

function isTypingTarget(target: EventTarget | null): boolean {
    if (!(target instanceof HTMLElement)) return false
    const tag = target.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
    if (target.isContentEditable) return true
    return false
}

export default function GlobalShortcuts() {
    const router = useRouter()
    const pathname = usePathname()
    const [paletteOpen, setPaletteOpen] = useState(false)
    const [shortcutsOpen, setShortcutsOpen] = useState(false)

    // `g`-prefix chord state. We use a ref instead of useState because
    // the keydown handler reads/writes from inside an event listener
    // that doesn't re-bind on every render — useState would close over
    // a stale value.
    const chordPrimedRef = useRef(false)
    const chordTimerRef = useRef<number | null>(null)

    const resetChord = useCallback(() => {
        chordPrimedRef.current = false
        if (chordTimerRef.current !== null) {
            window.clearTimeout(chordTimerRef.current)
            chordTimerRef.current = null
        }
    }, [])

    useEffect(() => {
        function handleKeyDown(event: KeyboardEvent) {
            // Cmd-K / Ctrl-K — open palette. Allowed even while typing
            // in an input (matches macOS/SaaS convention).
            if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
                event.preventDefault()
                setPaletteOpen((prev) => !prev)
                return
            }

            // Esc — close topmost modal (palette wins; cmdk also handles
            // its own Esc but this catches the case where the modal is
            // open and focus has wandered).
            if (event.key === 'Escape') {
                if (paletteOpen) {
                    setPaletteOpen(false)
                    return
                }
                if (shortcutsOpen) {
                    setShortcutsOpen(false)
                    return
                }
                return
            }

            // Everything below requires the user NOT be typing.
            if (isTypingTarget(event.target)) return

            // While a modal is open, suppress chord/help shortcuts so
            // typing in the palette's search field doesn't trigger nav.
            if (paletteOpen || shortcutsOpen) return

            // `?` (Shift+/) — open shortcuts help modal
            if (event.key === '?') {
                event.preventDefault()
                setShortcutsOpen(true)
                resetChord()
                return
            }

            // `/` — focus the search input on the analyses page
            if (event.key === '/' && pathname === '/analyses') {
                const searchInput = document.querySelector<HTMLElement>('[aria-label="Search analyses"]')
                if (searchInput) {
                    event.preventDefault()
                    searchInput.focus()
                    resetChord()
                    return
                }
            }

            // `g`-prefix chord
            if (event.key === 'g' && !chordPrimedRef.current) {
                chordPrimedRef.current = true
                chordTimerRef.current = window.setTimeout(resetChord, CHORD_TIMEOUT_MS)
                return
            }

            if (chordPrimedRef.current) {
                const destination = NAV_CHORDS[event.key]
                resetChord()
                if (destination) {
                    event.preventDefault()
                    router.push(destination)
                }
                return
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [paletteOpen, shortcutsOpen, pathname, router, resetChord])

    // Reset chord state on unmount (cleanup safety)
    useEffect(() => () => resetChord(), [resetChord])

    return (
        <>
            <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
            <KeyboardShortcutsModal open={shortcutsOpen} onOpenChange={setShortcutsOpen} />
        </>
    )
}
