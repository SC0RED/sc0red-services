'use client'

import { getRiskTierLabel } from '@/lib/utils/riskUtils'

const TIER_OPTIONS = ['critical', 'high', 'moderate', 'low'] as const
const TYPE_OPTIONS = ['portfolio', 'standalone'] as const

interface AnalysesToolbarProps {
    search: string
    onSearchChange: (value: string) => void
    tierFilter: string | null
    onTierFilterChange: (tier: string | null) => void
    typeFilter: string | null
    onTypeFilterChange: (type: string | null) => void
    filteredCount: number
    totalCount: number
    onClearAll: () => void
}

export default function AnalysesToolbar({
    search,
    onSearchChange,
    tierFilter,
    onTierFilterChange,
    typeFilter,
    onTypeFilterChange,
    filteredCount,
    totalCount,
    onClearAll,
}: AnalysesToolbarProps) {
    const hasActiveFilters = Boolean(tierFilter || typeFilter || search)

    return (
        <>
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
                        onChange={(e) => onSearchChange(e.target.value)}
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
                            onClick={() => onTierFilterChange(tierFilter === tier ? null : tier)}
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
                            onClick={() => onTypeFilterChange(typeFilter === type ? null : type)}
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
                    {filteredCount === totalCount
                        ? `${totalCount} analyses`
                        : `${filteredCount} of ${totalCount}`}
                </span>
            </div>

            {/* Clear Filters */}
            {hasActiveFilters && (
                <div style={{ marginBottom: '0.75rem' }}>
                    <button
                        type="button"
                        className="btn btn-ghost"
                        style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
                        onClick={onClearAll}
                    >
                        Clear all filters
                    </button>
                </div>
            )}
        </>
    )
}
