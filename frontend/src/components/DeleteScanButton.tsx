'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

import { useToast } from '@/components/ui'

/**
 * Delete a scan with a 5-second Undo window via toast. Same deferred-
 * commit pattern as `DeleteAnalysisButton`. The cascade message is
 * explicit about what's being deleted ("scan + N analyses") so the
 * user can recognize the scope of the action before the window closes.
 *
 * Pass `redirectTo` to navigate after the commit lands — the portfolio
 * page uses this to bounce to /dashboard, since the page it's rendered
 * on just got tombstoned and would 404 on `router.refresh()`. Without
 * `redirectTo`, the default is `router.refresh()` to re-fetch the
 * current view (correct for the dashboard's Recent Scans table).
 *
 * Optional `label` and `variant='primary'` switch the visual treatment
 * for surfaces where the icon-only ghost button is too subtle (e.g.
 * the portfolio page header, where a "Delete portfolio" call-to-action
 * is the right primary action).
 */
export default function DeleteScanButton({
    scanId,
    companyCount,
    redirectTo,
    label,
    variant = 'icon',
}: {
    scanId: string
    /** Number of analyses that will be deleted with the scan. */
    companyCount?: number
    /** Path to navigate to after a successful delete. Default: refresh current page. */
    redirectTo?: string
    /** Label rendered next to (or instead of) the icon. Required when variant='primary'. */
    label?: string
    /** Visual variant. `icon` is the dashboard table style; `primary` is for top-level CTAs. */
    variant?: 'icon' | 'primary'
}) {
    const router = useRouter()
    const toast = useToast()
    const [deleting, setDeleting] = useState(false)

    function buildMessage(): string {
        if (typeof companyCount === 'number' && companyCount > 0) {
            const noun = companyCount === 1 ? 'analysis' : 'analyses'
            return `Deleted scan + ${companyCount} ${noun}`
        }
        return 'Deleted scan'
    }

    function handleDeleteClick() {
        if (deleting) return
        setDeleting(true)
        toast.undo({
            message: buildMessage(),
            onCommit: async () => {
                try {
                    const response = await fetch(`/api/scan/${scanId}`, { method: 'DELETE' })
                    if (!response.ok) {
                        toast.error('Failed to delete scan')
                        setDeleting(false)
                        return
                    }
                    if (redirectTo) {
                        router.push(redirectTo)
                    } else {
                        router.refresh()
                    }
                } catch {
                    toast.error('Network error deleting scan')
                    setDeleting(false)
                }
            },
            onUndo: () => {
                setDeleting(false)
            },
        })
    }

    if (variant === 'primary') {
        return (
            <button
                onClick={handleDeleteClick}
                disabled={deleting}
                className="btn btn-ghost btn-sm"
                title={deleting ? 'Deleting...' : 'Delete scan'}
                aria-label={label ?? 'Delete scan'}
                style={{
                    color: 'var(--accent-red, #c1432a)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    padding: '0.4rem 0.75rem',
                    opacity: deleting ? 0.5 : 1,
                    cursor: deleting ? 'not-allowed' : 'pointer',
                }}
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
                >
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                </svg>
                {label ?? 'Delete'}
            </button>
        )
    }

    return (
        <button
            onClick={handleDeleteClick}
            disabled={deleting}
            className="btn btn-ghost btn-sm"
            title={deleting ? 'Deleting...' : 'Delete scan'}
            aria-label="Delete scan"
            style={{
                color: 'var(--text-tertiary)',
                padding: '0.25rem 0.5rem',
                opacity: deleting ? 0.5 : 1,
                cursor: deleting ? 'not-allowed' : 'pointer',
            }}
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
            >
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
        </button>
    )
}
