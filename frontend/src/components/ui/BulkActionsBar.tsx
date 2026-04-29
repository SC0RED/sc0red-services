'use client'

import Link from 'next/link'

interface BulkActionsBarProps {
    /** Number of selected items currently visible in the active view. */
    count: number
    /** Clears the selection. */
    onClear: () => void
    /** Triggers the bulk-delete flow (optimistic remove + Toast Undo). */
    onDelete?: () => void
    /**
     * If provided, renders a "Compare N" link to this href. Pass `undefined`
     * when comparison isn't applicable (e.g., count outside 2-3 on the
     * analyses page).
     */
    compareHref?: string
    /**
     * Disables the Delete button — used while a prior bulk-delete commit
     * is mid-flight to prevent rapid double-invocation racing on the same
     * selection. Default: `false`.
     */
    deleteDisabled?: boolean
    /**
     * Triggers the bulk-restore flow on the Recently Deleted admin page.
     * When provided, renders a "Restore N" primary button instead of —
     * or alongside — Delete. Per `recently-deleted-admin-ui` D7.
     */
    onRestore?: () => void
    /**
     * Disables the Restore button while a prior commit is in flight.
     * Default: `false`.
     */
    restoreDisabled?: boolean
    /**
     * Label-prefix for the Restore button. Default: `Restore` →
     * "Restore N". Override when the action surface needs different
     * copy (rare).
     */
    restoreLabel?: string
}

/**
 * Sticky bottom-of-viewport action bar that appears when one or more rows
 * are selected. Hosts the bulk actions for the analyses list — Clear,
 * Delete N, optionally Compare N — and now also Restore N for the
 * Recently Deleted admin page.
 *
 * Renders nothing when `count === 0` so callers can mount the bar
 * unconditionally and let it self-gate on selection.
 *
 * Per `webapp-ux-foundations-tier2` §3 D4 (Delete) and
 * `recently-deleted-admin-ui` D7 (Restore extension).
 */
export default function BulkActionsBar({
    count,
    onClear,
    onDelete,
    compareHref,
    deleteDisabled = false,
    onRestore,
    restoreDisabled = false,
    restoreLabel = 'Restore',
}: BulkActionsBarProps) {
    if (count === 0) return null

    return (
        <div
            className="bulk-actions-bar"
            role="region"
            aria-label="Bulk actions"
            // Live region so screen readers announce the count change.
            aria-live="polite"
        >
            <span className="bulk-actions-bar-count">{count} selected</span>
            <div className="bulk-actions-bar-actions">
                {compareHref && (
                    <Link href={compareHref} className="btn btn-secondary btn-sm">
                        Compare {count}
                    </Link>
                )}
                {onRestore && (
                    <button
                        type="button"
                        onClick={onRestore}
                        disabled={restoreDisabled}
                        className="btn btn-primary btn-sm"
                        aria-label={`${restoreLabel} ${count} selected records`}
                        style={restoreDisabled ? { opacity: 0.5, cursor: 'not-allowed' } : undefined}
                    >
                        {restoreLabel} {count}
                    </button>
                )}
                {onDelete && (
                    <button
                        type="button"
                        onClick={onDelete}
                        disabled={deleteDisabled}
                        className="btn btn-secondary btn-sm bulk-actions-bar-delete"
                        aria-label={`Delete ${count} selected analyses`}
                        style={deleteDisabled ? { opacity: 0.5, cursor: 'not-allowed' } : undefined}
                    >
                        Delete {count}
                    </button>
                )}
                <button
                    type="button"
                    onClick={onClear}
                    className="btn btn-ghost btn-sm"
                    aria-label="Clear selection"
                >
                    Clear
                </button>
            </div>
        </div>
    )
}
