import { render, type RenderOptions, type RenderResult } from '@testing-library/react'
import type { ReactElement } from 'react'

import { ToastProvider } from '@/components/ui/Toast'

/**
 * Render a UI element wrapped in the providers required for any
 * component that may use `useToast()`.
 *
 * Use this in any test that imports a component which calls `useToast`
 * (directly or transitively) — without the provider, the hook throws
 * by design (see `useToast must be used within a <ToastProvider>`).
 */
export function renderWithProviders(
    ui: ReactElement,
    options?: Omit<RenderOptions, 'wrapper'>
): RenderResult {
    return render(ui, { wrapper: ToastProvider, ...options })
}
