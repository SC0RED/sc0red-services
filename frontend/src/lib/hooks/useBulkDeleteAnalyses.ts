'use client'

import { useCallback, useState } from 'react'
import { useRouter } from 'next/navigation'

import { useToast } from '@/components/ui'
import type { AnalysisItem } from '@/lib/types/api'

interface UseBulkDeleteAnalysesArgs {
    /** Current local copy of the analyses list (the optimistic source). */
    rows: AnalysisItem[]
    /**
     * Updater for the local copy. The hook calls it to remove rows
     * optimistically on click, restore on Undo, and partial-restore
     * on commit failure.
     */
    setRows: (updater: (prev: AnalysisItem[]) => AnalysisItem[]) => void
    /**
     * Fired once at trigger time so the caller can clear selection state
     * (and any UI affordances tied to it). Not called on Undo — the rows
     * come back but the user's prior selection has already been cleared.
     */
    onAfterTrigger: () => void
}

/**
 * Hook that owns the bulk-delete-with-Undo flow for the analyses list.
 *
 * Flow:
 *   1. Caller invokes `handleBulkDelete(ids)`.
 *   2. Hook snapshots the targeted rows, optimistically filters them out
 *      of `rows`, and fires `onAfterTrigger()` so the caller can clear
 *      selection.
 *   3. A Toast Undo appears with a 5s window.
 *   4a. User clicks Undo → `onUndo` restores the rows.
 *   4b. User waits → `onCommit` issues a single
 *       `POST /api/analyses/bulk-delete` with the full id list. The
 *       backend deletes all analyses, then makes the cascade-to-scan
 *       decision in a single post-delete pass — race-immune. On full
 *       success, `router.refresh()` to pull authoritative data. On
 *       partial failure (cross-org / not-found ids), only those rows
 *       are restored. On full failure (network error), all rows are
 *       restored and an error toast surfaces.
 *
 * Why one bulk request instead of N parallel single-deletes: parallel
 * `DELETE /api/analysis/{id}` calls had each request running its own
 * cascade-check independently. When peer requests' unlinks hadn't yet
 * committed at read time, multiple requests could each conclude "the
 * scan still has linked companies" and none would delete it — leaving
 * orphan scans whose companies were all gone. Collapsing the cascade
 * decision into one handler run on the server side eliminates the race.
 *
 * The `deleting` flag returned from the hook is set on trigger and cleared
 * on Undo / commit. Callers MUST disable the trigger surface (Delete N
 * button) while `deleting === true` to prevent rapid double-invocation —
 * without that guard the same selection could fire two parallel commit
 * paths that race on `setRows` and create duplicate rows on Undo.
 *
 * Restoration ordering caveat: failed-to-delete rows are appended to the
 * end of `rows`, not their original positions. After a partial success
 * the hook calls `router.refresh()` so the server returns authoritative
 * order — there's a brief flash of mis-ordered rows before that lands.
 * Pure-network-error path has no router.refresh, so the mis-order persists
 * until the user navigates or refreshes manually. Acceptable v1 cost; a
 * future iteration could splice rows back at their original index.
 */
export function useBulkDeleteAnalyses({ rows, setRows, onAfterTrigger }: UseBulkDeleteAnalysesArgs) {
    const router = useRouter()
    const toast = useToast()
    const [deleting, setDeleting] = useState(false)

    const handleBulkDelete = useCallback(
        (ids: string[]) => {
            if (deleting || ids.length === 0) return

            const targetedIdSet = new Set(ids)
            const targetedRows = rows.filter((row) => targetedIdSet.has(row.id))
            setRows((prev) => prev.filter((row) => !targetedIdSet.has(row.id)))
            setDeleting(true)
            onAfterTrigger()

            const noun = ids.length === 1 ? 'analysis' : 'analyses'
            toast.undo({
                message: `Deleted ${ids.length} ${noun} and their reports`,
                onCommit: async () => {
                    // Single bulk POST — the backend's race-immune cascade
                    // depends on this being one handler run, not N parallel
                    // ones. Earlier versions of this hook fired
                    // `Promise.all` of N `DELETE /api/analysis/{id}` calls
                    // and produced orphan scans on shared-scan deletes (see
                    // bulk-delete-cascade-race fix in the architecture).
                    try {
                        const response = await fetch('/api/analyses/bulk-delete', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ ids }),
                        })
                        if (!response.ok) {
                            throw new Error(`Bulk delete failed: ${response.status}`)
                        }
                        const payload = (await response.json()) as {
                            deleted: string[]
                            failed: { id: string; reason: string }[]
                        }
                        if (payload.failed.length === 0) {
                            router.refresh()
                            return
                        }
                        // Partial failure — restore only the rows the server
                        // couldn't delete (e.g. cross-org / not-found).
                        const failedIds = new Set(payload.failed.map((entry) => entry.id))
                        const rowsToRestore = targetedRows.filter((row) => failedIds.has(row.id))
                        setRows((prev) => [...prev, ...rowsToRestore])
                        toast.error(
                            payload.failed.length === 1
                                ? 'Failed to delete 1 analysis — restored.'
                                : `Failed to delete ${payload.failed.length} analyses — restored.`
                        )
                        if (payload.deleted.length > 0) {
                            // At least one delete landed — refresh so the
                            // server's authoritative ordering replaces the
                            // append-at-end restoration.
                            router.refresh()
                        }
                    } catch {
                        setRows((prev) => [...prev, ...targetedRows])
                        toast.error(
                            ids.length === 1
                                ? 'Network error deleting analysis — restored.'
                                : `Network error deleting ${ids.length} analyses — restored.`
                        )
                    } finally {
                        setDeleting(false)
                    }
                },
                onUndo: () => {
                    setRows((prev) => [...prev, ...targetedRows])
                    setDeleting(false)
                },
            })
        },
        [deleting, rows, setRows, onAfterTrigger, router, toast]
    )

    return { handleBulkDelete, deleting }
}
