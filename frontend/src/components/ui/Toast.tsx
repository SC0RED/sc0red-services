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
 *   // Deferred-commit Undo (e.g., delete with safety net):
 *   toast.undo({
 *       message: 'Deleted Acme Corp',
 *       onCommit: () => fetch(`/api/analysis/${id}`, { method: 'DELETE' }),
 *       onUndo: () => { /* nothing — DELETE never fires *\/ },
 *   })
 *
 * Mount the `<ToastProvider>` once near the root of the React tree. The
 * `<ToastViewport>` portal is rendered by the provider, so a single
 * provider is enough.
 */

export type ToastVariant = 'success' | 'error' | 'info' | 'loading'

interface ToastAction {
    label: string
    onClick: () => void
}

export interface ToastItem {
    id: string
    variant: ToastVariant
    message: string
    description?: string
    /** Optional inline action button (e.g., "Undo") rendered before the close button. */
    action?: ToastAction
    /**
     * Override the default 4s auto-dismiss timer. Used by `toast.undo`
     * to give the user a longer (5s) commit window. Ignored for variants
     * that don't auto-dismiss (error, loading).
     */
    autoDismissMs?: number
    /**
     * Called when the auto-dismiss timer fires (i.e., the user did NOT
     * interact with the toast). Used by `toast.undo` to commit the
     * deferred action when the user lets the window expire.
     *
     * NOT called when the user clicks an action button or the close
     * button — those paths are explicit user choices, not auto-dismiss.
     */
    onAutoDismiss?: () => void
}

interface UpdatableToastFields {
    variant?: ToastVariant
    message?: string
    description?: string
}

export interface UndoToastOptions {
    message: string
    description?: string
    /** Runs when the auto-dismiss timer expires (default 5s). */
    onCommit: () => void
    /** Runs when the user clicks "Undo". Mutually exclusive with onCommit. */
    onUndo: () => void
    /** Override the default 5-second commit window. */
    durationMs?: number
}

export interface ToastApi {
    success: (message: string, description?: string) => string
    error: (message: string, description?: string) => string
    info: (message: string, description?: string) => string
    loading: (message: string, description?: string) => string
    /**
     * Show a toast with an inline "Undo" button and a deferred-commit
     * pattern: the toast appears immediately, but the actual side effect
     * (the API call, navigation, etc.) is delayed until the auto-dismiss
     * timer expires. If the user clicks "Undo" within the window, the
     * commit is cancelled — onUndo runs, onCommit never does.
     *
     * Closing the toast manually treats the close as an early commit
     * (the user has acknowledged the action and doesn't want to undo).
     */
    undo: (options: UndoToastOptions) => string
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
const UNDO_WINDOW_MS = 5000

export function ToastProvider({ children }: { children: React.ReactNode }) {
    const [toasts, setToasts] = useState<ToastItem[]>([])

    const dismiss = useCallback((id: string) => {
        setToasts((current) => current.filter((toast) => toast.id !== id))
    }, [])

    const enqueueRaw = useCallback((toast: Omit<ToastItem, 'id'>) => {
        const id = generateToastId()
        setToasts((current) => [...current, { ...toast, id }])
        return id
    }, [])

    const update = useCallback((id: string, fields: UpdatableToastFields) => {
        setToasts((current) => current.map((toast) => (toast.id === id ? { ...toast, ...fields } : toast)))
    }, [])

    const api = useMemo<ToastApi>(() => {
        const enqueue = (variant: ToastVariant, message: string, description?: string) =>
            enqueueRaw({ variant, message, description })

        return {
            success: (message, description) => enqueue('success', message, description),
            error: (message, description) => enqueue('error', message, description),
            info: (message, description) => enqueue('info', message, description),
            loading: (message, description) => enqueue('loading', message, description),
            undo: (options) => {
                // Track whether the action button was clicked so the timer
                // effect (which fires `onAutoDismiss`) knows to skip the
                // commit. The closure captures these refs at creation time.
                let cancelled = false
                return enqueueRaw({
                    variant: 'success',
                    message: options.message,
                    description: options.description,
                    autoDismissMs: options.durationMs ?? UNDO_WINDOW_MS,
                    onAutoDismiss: () => {
                        if (!cancelled) options.onCommit()
                    },
                    action: {
                        label: 'Undo',
                        onClick: () => {
                            cancelled = true
                            options.onUndo()
                        },
                    },
                })
            },
            update,
            dismiss,
        }
    }, [enqueueRaw, update, dismiss])

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

    // Stable callback refs so the timer effect doesn't re-bind every render.
    const dismissRef = useRef(onDismiss)
    const onAutoDismissRef = useRef(toast.onAutoDismiss)
    useEffect(() => {
        dismissRef.current = onDismiss
    }, [onDismiss])
    useEffect(() => {
        onAutoDismissRef.current = toast.onAutoDismiss
    }, [toast.onAutoDismiss])

    useEffect(() => {
        if (!shouldAutoDismiss) return
        const duration = toast.autoDismissMs ?? AUTO_DISMISS_MS
        const handle = window.setTimeout(() => {
            onAutoDismissRef.current?.()
            dismissRef.current()
        }, duration)
        return () => window.clearTimeout(handle)
    }, [shouldAutoDismiss, toast.variant, toast.message, toast.autoDismissMs])

    const role = toast.variant === 'error' ? 'alert' : 'status'

    /**
     * Close-button click semantics for undo toasts: treat as "commit
     * early." The user explicitly acknowledged the action and chose
     * not to undo, so we run the deferred commit immediately rather
     * than discarding it silently. For non-undo toasts (no
     * onAutoDismiss), this collapses to a plain dismiss.
     */
    function handleCloseClick() {
        toast.onAutoDismiss?.()
        onDismiss()
    }

    return (
        <div className={`toast toast-${toast.variant}`} role={role} data-variant={toast.variant}>
            <div className="toast-content">
                <div className="toast-message">{toast.message}</div>
                {toast.description && <div className="toast-description">{toast.description}</div>}
            </div>
            {toast.action && (
                <button
                    type="button"
                    className="toast-action"
                    onClick={() => {
                        toast.action?.onClick()
                        // The action's onClick is responsible for any
                        // cancellation flag (toast.undo sets one). We
                        // dismiss the toast — the auto-dismiss timer's
                        // commit will be skipped because the action ran
                        // first.
                        onDismiss()
                    }}
                >
                    {toast.action.label}
                </button>
            )}
            <button
                type="button"
                className="toast-close"
                aria-label="Dismiss notification"
                onClick={handleCloseClick}
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
