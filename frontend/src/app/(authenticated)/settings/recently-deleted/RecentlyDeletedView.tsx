'use client'

import Link from 'next/link'
import { useCallback, useMemo, useState } from 'react'

import BulkActionsBar from '@/components/ui/BulkActionsBar'
import RelativeTime from '@/components/ui/RelativeTime'
import { useToast } from '@/components/ui'
import type {
    RecentlyDeletedRecord,
    RecentlyDeletedResponse,
    RecentlyDeletedWindow,
    RestoreFailure,
    RestoreResponse,
} from '@/lib/types/api'

const WINDOW_OPTIONS: { value: RecentlyDeletedWindow; label: string }[] = [
    { value: '24h', label: '24h' },
    { value: '7d', label: '7d' },
    { value: '30d', label: '30d' },
    { value: '90d', label: '90d' },
]

interface Props {
    /** Records prefetched server-side for the default 30d window. */
    initialRecords: RecentlyDeletedRecord[]
}

/**
 * Phase 2 of soft-delete recovery — interactive admin surface for
 * restoring tombstoned scans + analyses within the 90-day TTL window.
 *
 * State:
 * - **window** — currently-selected time window chip; refetches on
 *   change. Default 30d (matches the server prefetch).
 * - **search** — client-side substring filter on `displayName`.
 * - **selected** — Set of selected record ids; drives `BulkActionsBar`.
 * - **records** — the live list. After a successful restore we refetch
 *   instead of optimistically removing — D5 in the design doc rejects
 *   optimistic removal; the success Toast plus the small refetch
 *   flicker is the right honesty trade-off.
 *
 * Failure shape: per-id failures from the backend's `failed` array
 * surface as a Toast error with the count + reason summary.
 */
export default function RecentlyDeletedView({ initialRecords }: Props) {
    const toast = useToast()
    const [records, setRecords] = useState<RecentlyDeletedRecord[]>(initialRecords)
    const [window, setWindow] = useState<RecentlyDeletedWindow>('30d')
    const [search, setSearch] = useState('')
    const [selected, setSelected] = useState<Set<string>>(new Set())
    const [restoring, setRestoring] = useState(false)

    const refetch = useCallback(
        async (target: RecentlyDeletedWindow) => {
            try {
                const response = await fetch(`/api/admin/recently-deleted?window=${target}`)
                if (!response.ok) {
                    toast.error('Failed to load recently-deleted records')
                    return
                }
                const data: RecentlyDeletedResponse = await response.json()
                setRecords(data.records)
                // Drop any selected ids that fell out of the new window
                // — keeping them would let the user accidentally restore
                // records they can no longer see.
                setSelected((prior) => {
                    const visibleIds = new Set(data.records.map((r) => r.id))
                    const next = new Set<string>()
                    for (const id of prior) {
                        if (visibleIds.has(id)) next.add(id)
                    }
                    return next
                })
            } catch {
                toast.error('Network error loading recently-deleted records')
            }
        },
        [toast]
    )

    const handleWindowChange = useCallback(
        (next: RecentlyDeletedWindow) => {
            if (next === window) return
            setWindow(next)
            void refetch(next)
        },
        [window, refetch]
    )

    const filtered = useMemo(() => {
        if (!search.trim()) return records
        const needle = search.toLowerCase()
        return records.filter((r) => r.displayName.toLowerCase().includes(needle))
    }, [records, search])

    const toggleSelected = useCallback((id: string) => {
        setSelected((prior) => {
            const next = new Set(prior)
            if (next.has(id)) {
                next.delete(id)
            } else {
                next.add(id)
            }
            return next
        })
    }, [])

    const clearSelection = useCallback(() => setSelected(new Set()), [])

    const summarizeFailures = useCallback((failures: RestoreFailure[]): string => {
        const expired = failures.filter((f) => f.reason === 'ttl_expired').length
        const notFound = failures.filter((f) => f.reason === 'not_found').length
        const parts: string[] = []
        if (expired > 0) parts.push(`${expired} expired (TTL)`)
        if (notFound > 0) parts.push(`${notFound} not found`)
        return parts.join(', ') || 'unknown failure'
    }, [])

    const restore = useCallback(
        async (ids: string[]) => {
            if (restoring || ids.length === 0) return
            setRestoring(true)
            const loadingToastId = toast.loading(
                ids.length === 1 ? 'Restoring 1 record…' : `Restoring ${ids.length} records…`
            )
            try {
                const response = await fetch('/api/admin/restore', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ids }),
                })
                toast.dismiss(loadingToastId)
                if (!response.ok) {
                    toast.error('Restore request failed')
                    return
                }
                const data: RestoreResponse = await response.json()
                if (data.failed.length === 0) {
                    toast.success(
                        data.restored.length === 1
                            ? 'Restored 1 record'
                            : `Restored ${data.restored.length} records`
                    )
                } else if (data.restored.length > 0) {
                    toast.error(
                        `Restored ${data.restored.length}, ${data.failed.length} failed: ${summarizeFailures(data.failed)}`
                    )
                } else {
                    toast.error(`Restore failed: ${summarizeFailures(data.failed)}`)
                }
                // Drop restored ids from selection before refetch so
                // the BulkActionsBar count reflects reality even if
                // refetch is in flight.
                setSelected((prior) => {
                    const next = new Set(prior)
                    for (const id of data.restored) next.delete(id)
                    return next
                })
                await refetch(window)
            } catch {
                toast.dismiss(loadingToastId)
                toast.error('Network error during restore')
            } finally {
                setRestoring(false)
            }
        },
        [restoring, refetch, summarizeFailures, toast, window]
    )

    const restoreSelected = useCallback(() => {
        restore(Array.from(selected))
    }, [restore, selected])

    if (records.length === 0) {
        return (
            <>
                <Header
                    window={window}
                    onWindowChange={handleWindowChange}
                    search={search}
                    onSearchChange={setSearch}
                />
                <EmptyState window={window} />
            </>
        )
    }

    return (
        <>
            <Header
                window={window}
                onWindowChange={handleWindowChange}
                search={search}
                onSearchChange={setSearch}
            />

            <div className="card" style={{ overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                            {['', 'Name', 'Type', 'Deleted by', 'Deleted', ''].map((h, i) => (
                                <th
                                    key={`${h}-${i}`}
                                    style={{
                                        padding: '0.875rem 1rem',
                                        textAlign: 'left',
                                        fontSize: '0.8125rem',
                                        fontWeight: 600,
                                        color: 'var(--text-secondary)',
                                        textTransform: 'uppercase',
                                        letterSpacing: '0.06em',
                                    }}
                                >
                                    {h}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {filtered.length === 0 ? (
                            <tr>
                                <td
                                    colSpan={6}
                                    style={{
                                        padding: '1.5rem',
                                        textAlign: 'center',
                                        color: 'var(--text-secondary)',
                                    }}
                                >
                                    No matches for &quot;{search}&quot; in the current window.
                                </td>
                            </tr>
                        ) : (
                            filtered.map((record, i) => (
                                <Row
                                    key={record.id}
                                    record={record}
                                    isLast={i === filtered.length - 1}
                                    selected={selected.has(record.id)}
                                    onToggle={() => toggleSelected(record.id)}
                                    onRestore={() => restore([record.id])}
                                    restoring={restoring}
                                />
                            ))
                        )}
                    </tbody>
                </table>
            </div>

            <BulkActionsBar
                count={selected.size}
                onClear={clearSelection}
                onRestore={restoreSelected}
                restoreDisabled={restoring}
                restoreLabel="Restore"
            />
        </>
    )
}

function Header({
    window,
    onWindowChange,
    search,
    onSearchChange,
}: {
    window: RecentlyDeletedWindow
    onWindowChange: (next: RecentlyDeletedWindow) => void
    search: string
    onSearchChange: (next: string) => void
}) {
    return (
        <div style={{ marginBottom: '1.5rem' }}>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.25rem' }}>Recently Deleted</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem', marginBottom: '1rem' }}>
                Restore scans and analyses deleted within the last 90 days. Records are automatically purged
                after 90 days.
            </p>

            <div
                style={{
                    display: 'flex',
                    gap: '0.75rem',
                    alignItems: 'center',
                    marginBottom: '1rem',
                    flexWrap: 'wrap',
                }}
            >
                <div role="group" aria-label="Time window" style={{ display: 'flex', gap: '0.25rem' }}>
                    {WINDOW_OPTIONS.map((option) => {
                        const active = option.value === window
                        return (
                            <button
                                key={option.value}
                                type="button"
                                onClick={() => onWindowChange(option.value)}
                                aria-pressed={active}
                                className={active ? 'btn btn-secondary btn-sm' : 'btn btn-ghost btn-sm'}
                                style={active ? undefined : { color: 'var(--text-secondary)' }}
                            >
                                {option.label}
                            </button>
                        )
                    })}
                </div>

                <input
                    type="search"
                    placeholder="Search by name…"
                    value={search}
                    onChange={(event) => onSearchChange(event.target.value)}
                    aria-label="Filter by name"
                    style={{
                        flex: 1,
                        minWidth: '200px',
                        padding: '0.5rem 0.75rem',
                        background: 'var(--bg-elevated)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: '6px',
                        color: 'var(--text-primary)',
                        fontSize: '0.9375rem',
                    }}
                />
            </div>
        </div>
    )
}

function EmptyState({ window }: { window: RecentlyDeletedWindow }) {
    const labels: Record<RecentlyDeletedWindow, string> = {
        '24h': '24 hours',
        '7d': '7 days',
        '30d': '30 days',
        '90d': '90 days',
    }
    return (
        <div
            className="card"
            style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}
        >
            <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                Nothing deleted in the last {labels[window]}
            </h2>
            <p style={{ fontSize: '0.9375rem' }}>
                Records that have been deleted in the past 90 days appear here so admins can restore them.{' '}
                <Link href="/analyses" style={{ color: 'var(--accent-blue)' }}>
                    Back to Analyses →
                </Link>
            </p>
        </div>
    )
}

function Row({
    record,
    isLast,
    selected,
    onToggle,
    onRestore,
    restoring,
}: {
    record: RecentlyDeletedRecord
    isLast: boolean
    selected: boolean
    onToggle: () => void
    onRestore: () => void
    restoring: boolean
}) {
    return (
        <tr style={isLast ? undefined : { borderBottom: '1px solid var(--border-subtle)' }}>
            <td style={{ padding: '0.875rem 1rem', width: '40px' }}>
                <input
                    type="checkbox"
                    checked={selected}
                    onChange={onToggle}
                    aria-label={`Select ${record.displayName}`}
                />
            </td>
            <td style={{ padding: '0.875rem 1rem' }}>
                <span style={{ fontWeight: 500 }}>{record.displayName || 'Unnamed'}</span>
                {record.parentTombstoned && (
                    <span
                        title="Parent scan was also deleted. Restoring this analysis will leave it without a scan link unless you also restore the scan."
                        style={{
                            marginLeft: '0.5rem',
                            padding: '0.125rem 0.5rem',
                            fontSize: '0.75rem',
                            color: 'var(--risk-warning, var(--text-secondary))',
                            background: 'var(--risk-warning-bg, var(--bg-elevated))',
                            borderRadius: '999px',
                        }}
                    >
                        ⚠ Parent also deleted
                    </span>
                )}
            </td>
            <td style={{ padding: '0.875rem 1rem' }}>
                <TypeBadge type={record.type} />
            </td>
            <td style={{ padding: '0.875rem 1rem', color: 'var(--text-secondary)' }}>
                {record.deletedBy?.name ?? 'Unknown'}
            </td>
            <td style={{ padding: '0.875rem 1rem', color: 'var(--text-secondary)' }}>
                <RelativeTime value={record.deletedAt} />
            </td>
            <td style={{ padding: '0.875rem 1rem', textAlign: 'right' }}>
                <button
                    type="button"
                    onClick={onRestore}
                    disabled={restoring}
                    className="btn btn-ghost btn-sm"
                    aria-label={`Restore ${record.displayName}`}
                    style={
                        restoring ? { opacity: 0.5, cursor: 'not-allowed' } : { color: 'var(--accent-blue)' }
                    }
                >
                    Restore
                </button>
            </td>
        </tr>
    )
}

function TypeBadge({ type }: { type: 'analysis' | 'scan' }) {
    const label = type === 'analysis' ? 'Analysis' : 'Portfolio scan'
    return (
        <span
            style={{
                padding: '0.125rem 0.5rem',
                fontSize: '0.75rem',
                fontWeight: 500,
                color: 'var(--text-secondary)',
                background: 'var(--bg-elevated)',
                borderRadius: '999px',
            }}
        >
            {label}
        </span>
    )
}
