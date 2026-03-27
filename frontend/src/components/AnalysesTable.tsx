'use client'

import { useState, useMemo } from 'react'
import Link from 'next/link'

import DeleteAnalysisButton from '@/components/DeleteAnalysisButton'
import AnalysesToolbar from '@/components/AnalysesToolbar'
import { SortableHeader, TableHeader } from '@/components/SortableHeader'
import type { SortField, SortDirection } from '@/components/SortableHeader'
import { exportAnalysesListCsv } from '@/lib/utils/csvExport'
import { getRiskTierLabel, TIER_COLORS } from '@/lib/utils/riskUtils'
import type { AnalysisItem } from '@/lib/types/api'

interface AnalysesTableProps {
    analyses: AnalysisItem[]
}

export default function AnalysesTable({ analyses }: AnalysesTableProps) {
    const [search, setSearch] = useState('')
    const [tierFilter, setTierFilter] = useState<string | null>(null)
    const [typeFilter, setTypeFilter] = useState<string | null>(null)
    const [sortField, setSortField] = useState<SortField>('analyzedAt')
    const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

    function toggleSelection(id: string) {
        setSelectedIds((prev) => {
            const next = new Set(prev)
            if (next.has(id)) {
                next.delete(id)
            } else if (next.size < 3) {
                next.add(id)
            }
            return next
        })
    }

    function toggleSelectAll() {
        if (selectedIds.size === filtered.length || selectedIds.size === 3) {
            setSelectedIds(new Set())
        } else {
            const ids = filtered.slice(0, 3).map((a) => a.id)
            setSelectedIds(new Set(ids))
        }
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

    // Only count selections that are visible in the current filtered view
    const visibleSelectedIds = useMemo(() => {
        const filteredIds = new Set(filtered.map((a) => a.id))
        return new Set([...selectedIds].filter((id) => filteredIds.has(id)))
    }, [selectedIds, filtered])

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
                <>
                    {visibleSelectedIds.size >= 2 && (
                        <div
                            style={{
                                position: 'sticky',
                                bottom: '1rem',
                                zIndex: 10,
                                display: 'flex',
                                justifyContent: 'center',
                                marginBottom: '1rem',
                            }}
                        >
                            <Link
                                href={`/analyses/compare?ids=${Array.from(visibleSelectedIds).join(',')}`}
                                className="btn btn-primary"
                                style={{
                                    boxShadow: '0 4px 20px rgba(59,123,246,0.4)',
                                    padding: '0.625rem 1.5rem',
                                }}
                            >
                                Compare {visibleSelectedIds.size} Selected
                            </Link>
                        </div>
                    )}

                    <div className="card" style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', minWidth: '800px', borderCollapse: 'collapse' }}>
                            <thead>
                                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                    <th style={{ padding: '0.875rem 0.75rem', width: '40px' }}>
                                        <input
                                            type="checkbox"
                                            checked={
                                                visibleSelectedIds.size > 0 &&
                                                visibleSelectedIds.size === Math.min(filtered.length, 3)
                                            }
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
                                    <TableHeader>Industry</TableHeader>
                                    <TableHeader>Source</TableHeader>
                                    <SortableHeader
                                        label="Risk Score"
                                        field="overallRiskScore"
                                        current={sortField}
                                        direction={sortDirection}
                                        onSort={handleSort}
                                    />
                                    <TableHeader>Tier</TableHeader>
                                    <SortableHeader
                                        label="Date"
                                        field="analyzedAt"
                                        current={sortField}
                                        direction={sortDirection}
                                        onSort={handleSort}
                                    />
                                    <th style={{ padding: '0.875rem 1.25rem' }} />
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map((a, i) => {
                                    const tier = a.riskTier ?? ''
                                    return (
                                        <tr
                                            key={a.id}
                                            style={{
                                                borderBottom:
                                                    i < filtered.length - 1
                                                        ? '1px solid var(--border-subtle)'
                                                        : 'none',
                                            }}
                                        >
                                            <td style={{ padding: '1rem 0.75rem', width: '40px' }}>
                                                <input
                                                    type="checkbox"
                                                    checked={selectedIds.has(a.id)}
                                                    onChange={() => toggleSelection(a.id)}
                                                    disabled={!selectedIds.has(a.id) && selectedIds.size >= 3}
                                                    aria-label={`Select ${a.companyName}`}
                                                    style={{
                                                        width: '16px',
                                                        height: '16px',
                                                        accentColor: 'var(--accent-blue)',
                                                        cursor:
                                                            selectedIds.has(a.id) || selectedIds.size < 3
                                                                ? 'pointer'
                                                                : 'not-allowed',
                                                    }}
                                                />
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                <div style={{ fontWeight: 500 }}>{a.companyName}</div>
                                                {a.companyUrl && (
                                                    <div
                                                        className="truncate"
                                                        style={{
                                                            fontSize: '0.8125rem',
                                                            color: 'var(--text-tertiary)',
                                                            maxWidth: '200px',
                                                        }}
                                                    >
                                                        {a.companyUrl}
                                                    </div>
                                                )}
                                            </td>
                                            <td
                                                style={{
                                                    padding: '1rem 1.25rem',
                                                    color: 'var(--text-secondary)',
                                                    fontSize: '0.875rem',
                                                }}
                                            >
                                                {a.industry || '—'}
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                <span
                                                    className={`badge badge-${a.scanType === 'portfolio' ? 'blue' : 'cyan'}`}
                                                    style={{ fontSize: '0.7rem' }}
                                                >
                                                    {a.scanType === 'portfolio' ? 'Portfolio' : 'Standalone'}
                                                </span>
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                <span
                                                    style={{
                                                        fontWeight: 700,
                                                        fontSize: '1.1rem',
                                                        color: TIER_COLORS[tier],
                                                    }}
                                                >
                                                    {a.overallRiskScore?.toFixed(1)}
                                                </span>
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                {tier && (
                                                    <span className={`badge badge-${tier}`}>
                                                        {getRiskTierLabel(tier)}
                                                    </span>
                                                )}
                                            </td>
                                            <td
                                                style={{
                                                    padding: '1rem 1.25rem',
                                                    color: 'var(--text-tertiary)',
                                                    fontSize: '0.8125rem',
                                                    whiteSpace: 'nowrap',
                                                }}
                                            >
                                                {a.analyzedAt
                                                    ? new Date(a.analyzedAt).toLocaleDateString()
                                                    : '—'}
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem', whiteSpace: 'nowrap' }}>
                                                <div
                                                    style={{
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        gap: '0.25rem',
                                                    }}
                                                >
                                                    <Link
                                                        href={`/analysis/${a.id}`}
                                                        className="btn btn-ghost btn-sm"
                                                    >
                                                        View
                                                    </Link>
                                                    <DeleteAnalysisButton
                                                        analysisId={a.id}
                                                        companyName={a.companyName}
                                                    />
                                                </div>
                                            </td>
                                        </tr>
                                    )
                                })}
                            </tbody>
                        </table>
                    </div>
                </>
            )}
        </div>
    )
}
