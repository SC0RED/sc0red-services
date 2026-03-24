import type { Company } from '@/lib/types/scan'

interface PortfolioConfirmPhaseProps {
    companies: Company[]
    onCompanyToggle: (index: number, selected: boolean) => void
    onConfirm: () => void
    onReset: () => void
}

export default function PortfolioConfirmPhase({
    companies,
    onCompanyToggle,
    onConfirm,
    onReset,
}: PortfolioConfirmPhaseProps) {
    const selectedCount = companies.filter((c) => c.selected).length

    return (
        <div>
            <div
                className="card"
                style={{
                    padding: '1.25rem 1.5rem',
                    marginBottom: '1.25rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '1rem',
                }}
            >
                <div
                    style={{
                        width: '40px',
                        height: '40px',
                        borderRadius: 'var(--radius-md)',
                        background: 'var(--risk-low-bg)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                    }}
                >
                    <svg
                        width="20"
                        height="20"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="var(--risk-low)"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                    >
                        <polyline points="20 6 9 17 4 12" />
                    </svg>
                </div>
                <div>
                    <div style={{ fontWeight: 600 }}>Portfolio companies discovered</div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                        Found {companies.length} companies. Review and deselect any you don&apos;t want to
                        analyze.
                    </div>
                </div>
            </div>

            <div
                style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.5rem',
                    marginBottom: '1.5rem',
                    maxHeight: '400px',
                    overflowY: 'auto',
                }}
            >
                {companies.map((company, i) => (
                    <div
                        key={company.url}
                        className="card-surface-2"
                        style={{
                            padding: '0.875rem 1rem',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.875rem',
                        }}
                    >
                        <input
                            type="checkbox"
                            id={`company-${i}`}
                            checked={company.selected}
                            onChange={(e) => onCompanyToggle(i, e.target.checked)}
                            style={{
                                width: '16px',
                                height: '16px',
                                accentColor: 'var(--accent-blue)',
                                cursor: 'pointer',
                            }}
                        />
                        <label htmlFor={`company-${i}`} style={{ flex: 1, cursor: 'pointer' }}>
                            <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>{company.name}</div>
                            <div
                                style={{
                                    color: 'var(--text-tertiary)',
                                    fontSize: '0.8125rem',
                                }}
                            >
                                {company.url}
                            </div>
                        </label>
                    </div>
                ))}
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                <button onClick={onConfirm} className="btn btn-primary">
                    Analyze {selectedCount} Companies
                </button>
                <button onClick={onReset} className="btn btn-ghost">
                    Start Over
                </button>
                <span
                    style={{
                        color: 'var(--text-tertiary)',
                        fontSize: '0.8125rem',
                        marginLeft: 'auto',
                    }}
                >
                    {selectedCount}/{companies.length} selected
                </span>
            </div>
        </div>
    )
}
