interface PortfolioProgressStripProps {
    completedCount: number
    totalCount: number
    visible: boolean
}

export default function PortfolioProgressStrip({
    completedCount,
    totalCount,
    visible,
}: PortfolioProgressStripProps) {
    if (!visible || totalCount === 0) return null

    const percent = Math.round((completedCount / totalCount) * 100)

    return (
        <div
            style={{
                marginBottom: '1.5rem',
                padding: '0.75rem 1rem',
                borderRadius: '8px',
                backgroundColor: 'var(--surface-2, rgba(255,255,255,0.04))',
            }}
        >
            <div
                style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '0.5rem',
                    fontSize: '0.8125rem',
                    color: 'var(--text-secondary)',
                }}
            >
                <span>
                    {completedCount} of {totalCount} done
                </span>
                <span>{percent}%</span>
            </div>
            <div
                style={{
                    height: '4px',
                    borderRadius: '2px',
                    backgroundColor: 'var(--border-subtle, rgba(255,255,255,0.08))',
                    overflow: 'hidden',
                }}
            >
                <div
                    style={{
                        height: '100%',
                        width: `${percent}%`,
                        borderRadius: '2px',
                        backgroundColor: 'var(--accent-blue, #3b82f6)',
                        transition: 'width 0.5s ease',
                    }}
                />
            </div>
        </div>
    )
}
