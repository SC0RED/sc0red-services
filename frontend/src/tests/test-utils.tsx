import { render, type RenderOptions, type RenderResult } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'

import { ToastProvider } from '@/components/ui/Toast'
import { ShortcutsUiProvider } from '@/components/ui/ShortcutsUi'

/**
 * All app-level providers a component under test may need: `useToast()`
 * (ToastProvider) and the shared command-palette / keyboard-shortcuts open-state
 * (ShortcutsUiProvider — used by GlobalShortcuts, the command palette, and the
 * sidebar footer affordance). Both throw by design when their hook is used
 * outside the provider.
 */
function AllProviders({ children }: { children: ReactNode }) {
    return (
        <ToastProvider>
            <ShortcutsUiProvider>{children}</ShortcutsUiProvider>
        </ToastProvider>
    )
}

export function renderWithProviders(
    ui: ReactElement,
    options?: Omit<RenderOptions, 'wrapper'>
): RenderResult {
    return render(ui, { wrapper: AllProviders, ...options })
}
