'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'

/**
 * Toast notification system.
 *
 * Variants:
 *   - `success` — auto-dismisses after 4s. role="status".
 *   - `info`    — auto-dismisses after 4s. role="status".
 *   - `loading` — does NOT auto-dismiss. role="status". Promote via `toast.update`.
 *   - `error`   — does NOT auto-dismiss (user must close). role="alert".
 *
 * Usage:
 *   const toast = useToast()
 *   toast.success("Deleted")
 *   const id = toast.loading("Re-analyzing...")
 *   await doWork()
 *   toast.update(id, { variant: 'success', message: 'Re-analysis queued' })
 *
 * Mount the `<ToastProvider>` once near the root of the React tree. The
 * `<ToastViewport>` portal is rendered by the provider, so a single
 * provider is enough.
 */

export type ToastVariant = 'success' | 'error' | 'info' | 'loading'

export interface ToastItem {
    id: string
    variant: ToastVariant
    message: string
    description?: string
}

interface UpdatableToastFields {
    variant?: ToastVariant
    message?: string
    description?: string
}

export interface ToastApi {
    success: (message: string, description?: string) => string
    error: (message: string, description?: string) => string
    info: (message: string, description?: string) => string
    loading: (message: string, description?: string) => string
    update: (id: string, fields: UpdatableToastFields) => void
    dismiss: (id: string) => void
}

const ToastContext = createContext<ToastApi | null>(null)

/** Hook to dispatch toasts from anywhere under `<ToastProvider>`. */
export function useToast(): ToastApi {
    const api = useContext(ToastContext)
    if (!api) {
        throw new Error('useToast must be used within a <ToastProvider>')
    }
    return api
}

/**
 * Generate a unique toast ID. Prefers `crypto.randomUUID()` (modern
 * runtimes); falls back to a timestamped random string for environments
 * where the API is unavailable (jsdom on older Node, etc.).
 */
function generateToastId(): string {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
        return crypto.randomUUID()
    }
    return `toast-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

const AUTO_DISMISS_MS = 4000

export function ToastProvider({ children }: { children: React.ReactNode }) {
    const [toasts, setToasts] = useState<ToastItem[]>([])

    const dismiss = useCallback((id: string) => {
        setToasts((current) => current.filter((toast) => toast.id !== id))
    }, [])

    const enqueue = useCallback((variant: ToastVariant, message: string, description?: string) => {
        const id = generateToastId()
        setToasts((current) => [...current, { id, variant, message, description }])
        return id
    }, [])

    const update = useCallback((id: string, fields: UpdatableToastFields) => {
        setToasts((current) => current.map((toast) => (toast.id === id ? { ...toast, ...fields } : toast)))
    }, [])

    const api = useMemo<ToastApi>(
        () => ({
            success: (message, description) => enqueue('success', message, description),
            error: (message, description) => enqueue('error', message, description),
            info: (message, description) => enqueue('info', message, description),
            loading: (message, description) => enqueue('loading', message, description),
            update,
            dismiss,
        }),
        [enqueue, update, dismiss]
    )

    return (
        <ToastContext.Provider value={api}>
            {children}
            <ToastViewport toasts={toasts} onDismiss={dismiss} />
        </ToastContext.Provider>
    )
}

function ToastViewport({ toasts, onDismiss }: { toasts: ToastItem[]; onDismiss: (id: string) => void }) {
    return (
        <div className="toast-viewport" aria-live="polite" aria-atomic="false">
            {toasts.map((toast) => (
                <Toast key={toast.id} toast={toast} onDismiss={() => onDismiss(toast.id)} />
            ))}
        </div>
    )
}

/**
 * One toast item. The wrapping `<div>` carries the variant-appropriate
 * ARIA role (`role="alert"` for errors, `role="status"` for the others)
 * so screen readers announce errors assertively and successes politely.
 *
 * Auto-dismiss is timer-based and only applies to success/info — loading
 * toasts persist until promoted via `toast.update`, errors persist until
 * the user closes them. Pause-on-hover is intentionally NOT implemented
 * for v1 (small polish to add later).
 */
export function Toast({ toast, onDismiss }: { toast: ToastItem; onDismiss: () => void }) {
    const shouldAutoDismiss = toast.variant === 'success' || toast.variant === 'info'

    // Stable callback ref so the timer effect doesn't re-bind every render.
    const dismissRef = useRef(onDismiss)
    useEffect(() => {
        dismissRef.current = onDismiss
    }, [onDismiss])

    useEffect(() => {
        if (!shouldAutoDismiss) return
        const handle = window.setTimeout(() => dismissRef.current(), AUTO_DISMISS_MS)
        return () => window.clearTimeout(handle)
    }, [shouldAutoDismiss, toast.variant, toast.message])

    const role = toast.variant === 'error' ? 'alert' : 'status'

    return (
        <div className={`toast toast-${toast.variant}`} role={role} data-variant={toast.variant}>
            <div className="toast-content">
                <div className="toast-message">{toast.message}</div>
                {toast.description && <div className="toast-description">{toast.description}</div>}
            </div>
            <button
                type="button"
                className="toast-close"
                aria-label="Dismiss notification"
                onClick={onDismiss}
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
    )
}
