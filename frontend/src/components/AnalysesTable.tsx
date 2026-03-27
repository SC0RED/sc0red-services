'use client'

import { useState, useMemo } from 'react'
import Link from 'next/link'

import DeleteAnalysisButton from '@/components/DeleteAnalysisButton'
import { getRiskTierLabel, TIER_COLORS } from '@/lib/utils/riskUtils'
import type { AnalysisItem } from '@/lib/types/api'

type SortField = 'companyName' | 'overallRiskScore' | 'analyzedAt'
type SortDirection = 'asc' | 'desc'

const TIER_OPTIONS = ['critical', 'high', 'moderate', 'low'] as const
const TYPE_OPTIONS = ['portfolio', 'standalone'] as const

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
            {/* Toolbar */}
            <div
                style={{
                    display: 'flex',
                    gap: '0.75rem',
                    marginBottom: '1rem',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                }}
            >
                {/* Search */}
                <div style={{ position: 'relative', flex: '1 1 240px', maxWidth: '320px' }}>
                    <svg
                        width="15"
                        height="15"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="var(--text-tertiary)"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        style={{
                            position: 'absolute',
                            left: '0.75rem',
                            top: '50%',
                            transform: 'translateY(-50%)',
                        }}
                    >
                        <circle cx="11" cy="11" r="8" />
                        <path d="m21 21-4.35-4.35" />
                    </svg>
                    <input
                        type="text"
                        className="input"
                        placeholder="Search by company or industry..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        aria-label="Search analyses"
                        style={{ paddingLeft: '2.5rem', fontSize: '0.8125rem' }}
                    />
                </div>

                {/* Tier Filter Chips */}
                <div style={{ display: 'flex', gap: '0.375rem', flexWrap: 'wrap' }}>
                    {TIER_OPTIONS.map((tier) => (
                        <button
                            key={tier}
                            type="button"
                            className={`badge badge-${tier}`}
                            onClick={() => setTierFilter(tierFilter === tier ? null : tier)}
                            aria-pressed={tierFilter === tier}
                            style={{
                                cursor: 'pointer',
                                opacity: tierFilter && tierFilter !== tier ? 0.4 : 1,
                                border:
                                    tierFilter === tier ? '2px solid currentColor' : '2px solid transparent',
                            }}
                        >
                            {getRiskTierLabel(tier)}
                        </button>
                    ))}
                </div>

                {/* Type Filter */}
                <div style={{ display: 'flex', gap: '0.375rem' }}>
                    {TYPE_OPTIONS.map((type) => (
                        <button
                            key={type}
                            type="button"
                            className={`badge badge-${type === 'portfolio' ? 'blue' : 'cyan'}`}
                            onClick={() => setTypeFilter(typeFilter === type ? null : type)}
                            aria-pressed={typeFilter === type}
                            style={{
                                cursor: 'pointer',
                                fontSize: '0.7rem',
                                opacity: typeFilter && typeFilter !== type ? 0.4 : 1,
                                border:
                                    typeFilter === type ? '2px solid currentColor' : '2px solid transparent',
                            }}
                        >
                            {type === 'portfolio' ? 'Portfolio' : 'Standalone'}
                        </button>
                    ))}
                </div>

                {/* Result count */}
                <span
                    style={{
                        fontSize: '0.8125rem',
                        color: 'var(--text-tertiary)',
                        marginLeft: 'auto',
                    }}
                >
                    {filtered.length === analyses.length
                        ? `${analyses.length} analyses`
                        : `${filtered.length} of ${analyses.length}`}
                </span>
            </div>

            {/* Active Filters Clear */}
            {(tierFilter || typeFilter || search) && (
                <div style={{ marginBottom: '0.75rem' }}>
                    <button
                        type="button"
                        className="btn btn-ghost"
                        style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
                        onClick={() => {
                            setSearch('')
                            setTierFilter(null)
                            setTypeFilter(null)
                        }}
                    >
                        Clear all filters
                    </button>
                </div>
            )}

            {/* Table */}
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
                                <th
                                    style={{
                                        padding: '0.875rem 1.25rem',
                                        textAlign: 'left',
                                        fontSize: '0.8125rem',
                                        fontWeight: 600,
                                        color: 'var(--text-secondary)',
                                        textTransform: 'uppercase',
                                        letterSpacing: '0.06em',
                                    }}
                                >
                                    Industry
                                </th>
                                <th
                                    style={{
                                        padding: '0.875rem 1.25rem',
                                        textAlign: 'left',
                                        fontSize: '0.8125rem',
                                        fontWeight: 600,
                                        color: 'var(--text-secondary)',
                                        textTransform: 'uppercase',
                                        letterSpacing: '0.06em',
                                    }}
                                >
                                    Source
                                </th>
                                <SortableHeader
                                    label="Risk Score"
                                    field="overallRiskScore"
                                    current={sortField}
                                    direction={sortDirection}
                                    onSort={handleSort}
                                />
                                <th
                                    style={{
                                        padding: '0.875rem 1.25rem',
                                        textAlign: 'left',
                                        fontSize: '0.8125rem',
                                        fontWeight: 600,
                                        color: 'var(--text-secondary)',
                                        textTransform: 'uppercase',
                                        letterSpacing: '0.06em',
                                    }}
                                >
                                    Tier
                                </th>
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
                                                    style={{
                                                        fontSize: '0.8125rem',
                                                        color: 'var(--text-tertiary)',
                                                        maxWidth: '200px',
                                                        overflow: 'hidden',
                                                        textOverflow: 'ellipsis',
                                                        whiteSpace: 'nowrap',
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
        <th
            style={{
                padding: '0.875rem 1.25rem',
                textAlign: 'left',
                fontSize: '0.8125rem',
                fontWeight: 600,
                color: 'var(--text-secondary)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                cursor: 'pointer',
                userSelect: 'none',
            }}
        >
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
