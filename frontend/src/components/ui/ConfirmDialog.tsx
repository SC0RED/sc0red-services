'use client'

import { useEffect } from 'react'

interface ConfirmDialogProps {
    open: boolean
    title: string
    message: string
    confirmLabel?: string
    cancelLabel?: string
    variant?: 'default' | 'danger'
    loading?: boolean
    onConfirm: () => void
    onCancel: () => void
}

export default function ConfirmDialog({
    open,
    title,
    message,
    confirmLabel = 'Confirm',
    cancelLabel = 'Cancel',
    variant = 'default',
    loading = false,
    onConfirm,
    onCancel,
}: ConfirmDialogProps) {
    // Close on Escape key
    useEffect(() => {
        if (!open) return

        function handleKeyDown(event: KeyboardEvent) {
            if (event.key === 'Escape') onCancel()
        }

        document.addEventListener('keydown', handleKeyDown)
        return () => document.removeEventListener('keydown', handleKeyDown)
    }, [open, onCancel])

    if (!open) return null

    return (
        <div className="confirm-dialog-backdrop" onClick={onCancel} role="presentation">
            <div
                className="confirm-dialog"
                role="alertdialog"
                aria-labelledby="confirm-dialog-title"
                aria-describedby="confirm-dialog-message"
                onClick={(event) => event.stopPropagation()}
            >
                <div className="confirm-dialog-content">
                    <h2 id="confirm-dialog-title" className="confirm-dialog-title">
                        {title}
                    </h2>
                    <p id="confirm-dialog-message" className="confirm-dialog-message">
                        {message}
                    </p>
                    <div className="confirm-dialog-actions">
                        <button className="btn btn-ghost btn-sm" onClick={onCancel} disabled={loading}>
                            {cancelLabel}
                        </button>
                        <button
                            className={`btn btn-${variant === 'danger' ? 'danger' : 'primary'} btn-sm`}
                            onClick={onConfirm}
                            disabled={loading}
                        >
                            {loading ? 'Processing...' : confirmLabel}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}
