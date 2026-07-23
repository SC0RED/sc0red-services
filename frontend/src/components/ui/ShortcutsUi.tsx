'use client'

import { createContext, useContext, useMemo, useState } from 'react'

/**
 * Shared open-state for the command palette and keyboard-shortcuts help modal.
 *
 * `GlobalShortcuts` owns the key bindings but the palette/help are now also
 * reachable by CLICK — from the sidebar footer affordance and (for the help) a
 * command-palette action. Lifting the open-state into this small context lets
 * those surfaces open the modals without duplicating state or re-implementing
 * the modals. `GlobalShortcuts` still renders the modals and owns Esc/precedence.
 *
 * `openPalette`/`openShortcuts` close the other modal first so only one is ever
 * open (matching the Esc precedence: palette > shortcuts).
 */
interface ShortcutsUi {
    paletteOpen: boolean
    shortcutsOpen: boolean
    setPaletteOpen: (open: boolean) => void
    setShortcutsOpen: (open: boolean) => void
    openPalette: () => void
    openShortcuts: () => void
}

const ShortcutsUiContext = createContext<ShortcutsUi | null>(null)

export function ShortcutsUiProvider({ children }: { children: React.ReactNode }) {
    const [paletteOpen, setPaletteOpen] = useState(false)
    const [shortcutsOpen, setShortcutsOpen] = useState(false)

    const value = useMemo<ShortcutsUi>(
        () => ({
            paletteOpen,
            shortcutsOpen,
            setPaletteOpen,
            setShortcutsOpen,
            openPalette: () => {
                setShortcutsOpen(false)
                setPaletteOpen(true)
            },
            openShortcuts: () => {
                setPaletteOpen(false)
                setShortcutsOpen(true)
            },
        }),
        [paletteOpen, shortcutsOpen]
    )

    return <ShortcutsUiContext.Provider value={value}>{children}</ShortcutsUiContext.Provider>
}

export function useShortcutsUi(): ShortcutsUi {
    const context = useContext(ShortcutsUiContext)
    if (!context) {
        throw new Error('useShortcutsUi must be used within a ShortcutsUiProvider')
    }
    return context
}
