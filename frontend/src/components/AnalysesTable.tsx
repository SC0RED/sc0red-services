'use client'

import { useState, useMemo } from 'react'
import Link from 'next/link'

import DeleteAnalysisButton from '@/components/DeleteAnalysisButton'
import AnalysesToolbar from '@/components/AnalysesToolbar'
import { getRiskTierLabel, TIER_COLORS } from '@/lib/utils/riskUtils'
import type { AnalysisItem } from '@/lib/types/api'

type SortField = 'companyName' | 'overallRiskScore' | 'analyzedAt'
type SortDirection = 'asc' | 'desc'

interface AnalysesTableProps {
    analyses: AnalysisItem[]
}

export default function AnalysesTable({ analyses }: AnalysesTableProps) {
    const [search, setSearch] = useState('')
    const [tierFilter, setTierFilter] = useState<string | null>(null)
    const [typeFilter, setTypeFilter] = useState<string | null>(null)
    const [sortField, setSortField] = useState<SortField>('analyzedAt')
    const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

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
                    <table style={{ width: '100%', minWidth: '860px', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
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
                                            {a.analyzedAt ? new Date(a.analyzedAt).toLocaleDateString() : '—'}
                                        </td>
                                        <td
                                            style={{
                                                padding: '1rem 1.25rem',
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '0.25rem',
                                            }}
                                        >
                                            <Link href={`/analysis/${a.id}`} className="btn btn-ghost btn-sm">
                                                View
                                            </Link>
                                            <DeleteAnalysisButton
                                                analysisId={a.id}
                                                companyName={a.companyName}
                                            />
                                        </td>
                                    </tr>
                                )
                            })}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    )
}

const HEADER_STYLE = {
    padding: '0.875rem 1.25rem',
    textAlign: 'left' as const,
    fontSize: '0.8125rem',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.06em',
}

function TableHeader({ children }: { children: React.ReactNode }) {
    return <th style={HEADER_STYLE}>{children}</th>
}

function SortableHeader({
    label,
    field,
    current,
    direction,
    onSort,
}: {
    label: string
    field: SortField
    current: SortField
    direction: SortDirection
    onSort: (field: SortField) => void
}) {
    const isActive = current === field
    return (
        <th style={{ ...HEADER_STYLE, cursor: 'pointer', userSelect: 'none' }}>
            <button
                type="button"
                onClick={() => onSort(field)}
                style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: isActive ? 'var(--accent-blue)' : 'var(--text-secondary)',
                    fontWeight: 600,
                    fontSize: '0.8125rem',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.375rem',
                    padding: 0,
                }}
                aria-label={`Sort by ${label}`}
            >
                {label}
                <span
                    style={{ fontSize: '0.625rem' }}
                    dangerouslySetInnerHTML={{
                        __html: isActive ? (direction === 'asc' ? '&#9650;' : '&#9660;') : '&#8597;',
                    }}
                />
            </button>
        </th>
    )
}
