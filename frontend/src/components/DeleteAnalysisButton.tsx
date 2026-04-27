'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

import { useToast } from '@/components/ui'

/**
 * Delete an analysis with a 5-second Undo window via toast.
 *
 * Flow:
 *   1. User clicks delete → button enters "deleting" state.
 *   2. Toast appears with "Deleted {company}. Undo?" + 5s timer.
 *   3a. User clicks Undo within 5s → no API call; button re-enables.
 *   3b. User waits 5s (or closes the toast) → DELETE fires; on success
 *       the page is refreshed (or the user is redirected); on failure
 *       an error toast surfaces and the analysis remains.
 *
 * The deferred-commit pattern (DELETE not fired until window expires)
 * means a quick ⌘R refresh during the window cancels the deletion
 * silently — acceptable for v1 per the design doc; server-side
 * soft-delete is a future improvement.
 */
export default function DeleteAnalysisButton({
    analysisId,
    companyName,
    variant = 'icon',
    redirectTo,
}: {
    analysisId: string
    companyName: string
    variant?: 'icon' | 'button'
    redirectTo?: string
}) {
    const router = useRouter()
    const toast = useToast()
    const [deleting, setDeleting] = useState(false)

    function handleDeleteClick() {
        if (deleting) return
        setDeleting(true)
        toast.undo({
            message: `Deleted ${companyName}`,
            onCommit: async () => {
                try {
                    const response = await fetch(`/api/analysis/${analysisId}`, {
                        method: 'DELETE',
                    })
                    if (!response.ok) {
                        toast.error(`Failed to delete ${companyName}`)
                        setDeleting(false)
                        return
                    }
                    if (redirectTo) {
                        router.push(redirectTo)
                    } else {
                        router.refresh()
                    }
                } catch {
                    toast.error(`Network error deleting ${companyName}`)
                    setDeleting(false)
                }
            },
            onUndo: () => {
                setDeleting(false)
            },
        })
    }

    if (variant === 'button') {
        return (
            <button
                onClick={handleDeleteClick}
                disabled={deleting}
                className="btn btn-ghost btn-sm"
                style={{ color: 'var(--risk-critical)', opacity: deleting ? 0.5 : 1 }}
            >
                {deleting ? 'Deleting...' : 'Delete Analysis'}
            </button>
        )
    }

    return (
        <button
            onClick={handleDeleteClick}
            disabled={deleting}
            title={deleting ? 'Deleting...' : 'Delete analysis'}
            aria-label={`Delete ${companyName}`}
            style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-primary)',
                padding: '0.375rem',
                borderRadius: 'var(--radius-sm)',
                cursor: deleting ? 'not-allowed' : 'pointer',
                opacity: deleting ? 0.5 : 1,
                display: 'inline-flex',
                alignItems: 'center',
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
