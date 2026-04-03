export type SortField = 'companyName' | 'overallRiskScore' | 'analyzedAt'
export type SortDirection = 'asc' | 'desc'

const HEADER_STYLE = {
    padding: '0.875rem 0.75rem',
    textAlign: 'left' as const,
    fontSize: '0.8125rem',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.06em',
}

export function TableHeader({ children }: { children: React.ReactNode }) {
    return <th style={HEADER_STYLE}>{children}</th>
}

export function SortableHeader({
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
                <span style={{ fontSize: '0.625rem' }}>
                    {isActive ? (direction === 'asc' ? '\u25B2' : '\u25BC') : '\u2195'}
                </span>
            </button>
        </th>
    )
}
