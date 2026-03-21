'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

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
    const [confirming, setConfirming] = useState(false)
    const [deleting, setDeleting] = useState(false)
    const [error, setError] = useState<string | null>(null)

    async function handleDelete() {
        setError(null)
        setDeleting(true)
        try {
            const res = await fetch(`/api/analysis/${analysisId}`, { method: 'DELETE' })
            if (!res.ok) {
                setError('Delete failed. Please try again.')
                return
            }
            if (redirectTo) {
                router.push(redirectTo)
            } else {
                router.refresh()
            }
        } catch {
            setError('Network error. Please try again.')
        } finally {
            setDeleting(false)
            setConfirming(false)
        }
    }

    if (confirming) {
        return (
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.375rem',
                    whiteSpace: 'nowrap',
                }}
            >
                <span
                    style={{
                        fontSize: '0.75rem',
                        color: 'var(--risk-critical)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        maxWidth: '120px',
                    }}
                >
                    Delete {companyName}?
                </span>
                <button
                    onClick={handleDelete}
                    disabled={deleting}
                    className="btn btn-sm"
                    style={{
                        background: 'var(--risk-critical)',
                        color: '#fff',
                        border: 'none',
                        fontSize: '0.75rem',
                        padding: '0.25rem 0.625rem',
                        opacity: deleting ? 0.6 : 1,
                    }}
                >
                    {deleting ? '...' : 'Yes'}
                </button>
                <button
                    onClick={() => setConfirming(false)}
                    disabled={deleting}
                    className="btn btn-ghost btn-sm"
                    style={{ fontSize: '0.75rem', padding: '0.25rem 0.625rem' }}
                >
                    No
                </button>
                {error && <span style={{ fontSize: '0.75rem', color: 'var(--risk-critical)' }}>{error}</span>}
            </div>
        )
    }

    if (variant === 'button') {
        return (
            <button
                onClick={() => setConfirming(true)}
                className="btn btn-ghost btn-sm"
                style={{ color: 'var(--risk-critical)' }}
            >
                Delete Analysis
            </button>
        )
    }

    return (
        <button
            onClick={() => setConfirming(true)}
            className="btn btn-ghost btn-sm"
            title="Delete analysis"
            style={{ color: 'var(--text-tertiary)', padding: '0.25rem 0.5rem' }}
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
