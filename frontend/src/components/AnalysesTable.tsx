'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'

import AnalysesToolbar from '@/components/AnalysesToolbar'
import AnalysisRow from '@/components/AnalysisRow'
import { SortableHeader, TableHeader } from '@/components/SortableHeader'
import type { SortField, SortDirection } from '@/components/SortableHeader'
import { BulkActionsBar } from '@/components/ui'
import { useBulkDeleteAnalyses } from '@/lib/hooks/useBulkDeleteAnalyses'
import { exportAnalysesListCsv } from '@/lib/utils/csvExport'
import type { AnalysisItem } from '@/lib/types/api'

interface AnalysesTableProps {
    analyses: AnalysisItem[]
}

/**
 * Compare action requires 2-3 analyses. The compare page (see
 * `/analyses/compare`) hard-rejects anything outside that band, so we
 * gate the Compare CTA on the same range here.
 */
const COMPARE_MIN = 2
const COMPARE_MAX = 3

export default function AnalysesTable({ analyses: initialAnalyses }: AnalysesTableProps) {
    // Local copy of the analyses array so bulk delete can optimistically
    // remove rows + restore them on Undo without waiting for a server
    // round-trip. After a successful commit `useBulkDeleteAnalyses` calls
    // `router.refresh()` so a subsequent navigation re-flows authoritative
    // server data.
    //
    // KNOWN: if the parent server component re-renders during the 5s undo
    // window from a cause OTHER than this hook's `router.refresh()` (e.g.,
    // a parallel re-analyze that also calls refresh), the sync effect
    // below restores the optimistic-removed rows visually for ~16ms before
    // the commit completes and re-removes them. In today's architecture
    // the parent only re-renders via router.refresh, and the only call
    // site for that is from this hook itself — so the race isn't currently
    // triggerable. Tracked for the future when more surfaces add refresh-
    // emitting actions. (Self-review minor #1 on PR #196.)
    const [analyses, setAnalyses] = useState<AnalysisItem[]>(initialAnalyses)
    useEffect(() => {
        setAnalyses(initialAnalyses)
    }, [initialAnalyses])

    const [search, setSearch] = useState('')
    const [tierFilter, setTierFilter] = useState<string | null>(null)
    const [typeFilter, setTypeFilter] = useState<string | null>(null)
    const [sortField, setSortField] = useState<SortField>('analyzedAt')
    const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

    // Anchor index for shift-click range selection (Linear/Gmail pattern).
    // Reset to null whenever the visible row order changes so a stale
    // anchor can't span across an unrelated layout.
    const lastClickedIndexRef = useRef<number | null>(null)

    const filtered = useMemo(() => {
        let result = analyses

        if (search.trim()) {
            const query = search.toLowerCase()
            result = result.filter(
                (a) =>
                    a.companyName.toLowerCase().includes(query) ||
                    (a.industry && a.industry.toLowerCase().includes(query))
            )
        }

        if (tierFilter) {
            result = result.filter((a) => a.riskTier === tierFilter)
        }

        if (typeFilter) {
            result = result.filter((a) => a.scanType === typeFilter)
        }

        return [...result].sort((a, b) => {
            const direction = sortDirection === 'asc' ? 1 : -1
            if (sortField === 'companyName') {
                return direction * a.companyName.localeCompare(b.companyName)
            }
            if (sortField === 'overallRiskScore') {
                return direction * ((a.overallRiskScore ?? 0) - (b.overallRiskScore ?? 0))
            }
            if (sortField === 'analyzedAt') {
                const dateA = a.analyzedAt ? new Date(a.analyzedAt).getTime() : 0
                const dateB = b.analyzedAt ? new Date(b.analyzedAt).getTime() : 0
                return direction * (dateA - dateB)
            }
            return 0
        })
    }, [analyses, search, tierFilter, typeFilter, sortField, sortDirection])

    // Filtering, sorting, or searching invalidates the row layout the
    // user was looking at — clear selection (and the shift-click anchor)
    // so a stale selection can't surprise the user with an off-screen
    // delete or compare action.
    const filterSignature = useMemo(
        () => `${search}|${tierFilter ?? ''}|${typeFilter ?? ''}|${sortField}|${sortDirection}`,
        [search, tierFilter, typeFilter, sortField, sortDirection]
    )
    const previousFilterSignatureRef = useRef(filterSignature)
    useEffect(() => {
        if (previousFilterSignatureRef.current !== filterSignature) {
            previousFilterSignatureRef.current = filterSignature
            setSelectedIds(new Set())
            lastClickedIndexRef.current = null
        }
    }, [filterSignature])

    function toggleSelectionAt(index: number, shiftKey: boolean) {
        const id = filtered[index].id
        // Shift-click: select every row from the anchor (last toggled)
        // through this index inclusive. Anchor stays put for chained
        // shift-clicks. If there's no anchor yet, behave like a normal
        // click and set this row as the anchor.
        if (shiftKey && lastClickedIndexRef.current !== null) {
            const start = Math.min(lastClickedIndexRef.current, index)
            const end = Math.max(lastClickedIndexRef.current, index)
            const rangeIds = filtered.slice(start, end + 1).map((a) => a.id)
            setSelectedIds((prev) => {
                const next = new Set(prev)
                for (const rangeId of rangeIds) next.add(rangeId)
                return next
            })
            return
        }
        setSelectedIds((prev) => {
            const next = new Set(prev)
            if (next.has(id)) next.delete(id)
            else next.add(id)
            return next
        })
        lastClickedIndexRef.current = index
    }

    function toggleSelectAll() {
        const allVisibleIds = filtered.map((a) => a.id)
        const allSelected = allVisibleIds.every((id) => selectedIds.has(id))
        if (allSelected) {
            setSelectedIds(new Set())
        } else {
            setSelectedIds(new Set(allVisibleIds))
        }
        lastClickedIndexRef.current = null
    }

    function handleSort(field: SortField) {
        if (sortField === field) {
            setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))
        } else {
            setSortField(field)
            setSortDirection(field === 'companyName' ? 'asc' : 'desc')
        }
    }

    function handleClearAll() {
        setSearch('')
        setTierFilter(null)
        setTypeFilter(null)
    }

    // Only count selections that are visible in the current filtered view.
    // Filter changes already clear `selectedIds` (above), so this is a
    // belt-and-braces guard against any future code path that mutates
    // selection without clearing.
    const visibleSelectedIds = useMemo(() => {
        const filteredIds = new Set(filtered.map((a) => a.id))
        return new Set([...selectedIds].filter((id) => filteredIds.has(id)))
    }, [selectedIds, filtered])

    const handleClearSelection = useCallback(() => {
        setSelectedIds(new Set())
        lastClickedIndexRef.current = null
    }, [])

    const { handleBulkDelete, deleting } = useBulkDeleteAnalyses({
        rows: analyses,
        setRows: setAnalyses,
        onAfterTrigger: handleClearSelection,
    })

    const compareHref =
        visibleSelectedIds.size >= COMPARE_MIN && visibleSelectedIds.size <= COMPARE_MAX
            ? `/analyses/compare?ids=${Array.from(visibleSelectedIds).join(',')}`
            : undefined

    const allVisibleSelected = filtered.length > 0 && filtered.every((a) => selectedIds.has(a.id))
    const someVisibleSelected = !allVisibleSelected && filtered.some((a) => selectedIds.has(a.id))

    return (
        <div>
            <AnalysesToolbar
                search={search}
                onSearchChange={setSearch}
                tierFilter={tierFilter}
                onTierFilterChange={setTierFilter}
                typeFilter={typeFilter}
                onTypeFilterChange={setTypeFilter}
                filteredCount={filtered.length}
                totalCount={analyses.length}
                onClearAll={handleClearAll}
            />

            {analyses.length > 0 && (
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '0.75rem' }}>
                    <button
                        type="button"
                        onClick={() => exportAnalysesListCsv(filtered)}
                        className="btn btn-ghost btn-sm"
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
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                            <polyline points="7 10 12 15 17 10" />
                            <line x1="12" y1="15" x2="12" y2="3" />
                        </svg>
                        Export CSV
                    </button>
                </div>
            )}

            {filtered.length === 0 ? (
                <div className="card" style={{ padding: '2rem', textAlign: 'center' }}>
                    <p style={{ color: 'var(--text-secondary)' }}>
                        {analyses.length === 0
                            ? 'No analyses yet. Run your first scan to get started.'
                            : 'No analyses match your filters.'}
                    </p>
                    {analyses.length === 0 && (
                        <Link href="/scan/new" className="btn btn-primary" style={{ marginTop: '1rem' }}>
                            Start a Scan
                        </Link>
                    )}
                </div>
            ) : (
                <div className="card" style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', minWidth: '1000px', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                <th style={{ padding: '0.875rem 0.5rem', width: '40px' }}>
                                    <input
                                        type="checkbox"
                                        checked={allVisibleSelected}
                                        ref={(el) => {
                                            // Indeterminate state when some (but not all) rows are
                                            // selected — visual cue without an extra prop.
                                            if (el) el.indeterminate = someVisibleSelected
                                        }}
                                        onChange={toggleSelectAll}
                                        aria-label="Select all analyses"
                                        style={{
                                            width: '16px',
                                            height: '16px',
                                            accentColor: 'var(--accent-blue)',
                                            cursor: 'pointer',
                                        }}
                                    />
                                </th>
                                <SortableHeader
                                    label="Company"
                                    field="companyName"
                                    current={sortField}
                                    direction={sortDirection}
                                    onSort={handleSort}
                                />
                                <TableHeader helpTerm="industry">Industry</TableHeader>
                                <TableHeader>Source</TableHeader>
                                <SortableHeader
                                    label="Risk Score"
                                    field="overallRiskScore"
                                    current={sortField}
                                    direction={sortDirection}
                                    onSort={handleSort}
                                    helpTerm="risk_score"
                                />
                                <TableHeader helpTerm="risk_tier">Tier</TableHeader>
                                <SortableHeader
                                    label="Date"
                                    field="analyzedAt"
                                    current={sortField}
                                    direction={sortDirection}
                                    onSort={handleSort}
                                />
                                <th style={{ padding: '0.875rem 0.5rem' }} />
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map((a, i) => (
                                <AnalysisRow
                                    key={a.id}
                                    analysis={a}
                                    selected={selectedIds.has(a.id)}
                                    onToggleSelection={(shiftKey) => toggleSelectionAt(i, shiftKey)}
                                    showBorder={i < filtered.length - 1}
                                />
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            <BulkActionsBar
                count={visibleSelectedIds.size}
                onClear={handleClearSelection}
                onDelete={() => handleBulkDelete(Array.from(visibleSelectedIds))}
                compareHref={compareHref}
                deleteDisabled={deleting}
            />
        </div>
    )
}
