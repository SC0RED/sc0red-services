import { useState } from 'react'

import AddCompanyForm from '@/components/scan/AddCompanyForm'
import CompanyListUpload from '@/components/scan/CompanyListUpload'
import DiscoveryVerdictBanner from '@/components/scan/DiscoveryVerdictBanner'
import type { Company, DiscoveryVerdict } from '@/lib/types/scan'

interface PortfolioConfirmPhaseProps {
    companies: Company[]
    verdict?: DiscoveryVerdict | null
    onCompanyToggle: (index: number, selected: boolean) => void
    onAddCompany: (name: string, url: string) => void
    /** Bulk-merge parsed uploads into the list; returns how many were newly
     *  added (the rest were dedup hits), so the uploader can report accurately. */
    onAddCompanies: (companies: Array<{ name: string; url: string }>) => number
    onConfirm: () => void
    onReset: () => void
}

export default function PortfolioConfirmPhase({
    companies,
    verdict,
    onCompanyToggle,
    onAddCompany,
    onAddCompanies,
    onConfirm,
    onReset,
}: PortfolioConfirmPhaseProps) {
    const selectedCount = companies.filter((c) => c.selected).length
    const [showUpload, setShowUpload] = useState(false)

    return (
        <div>
            {verdict ? (
                <DiscoveryVerdictBanner
                    verdict={verdict}
                    currentCount={companies.length}
                    onUploadList={() => setShowUpload((open) => !open)}
                    uploadOpen={showUpload}
                />
            ) : (
                <FallbackBanner count={companies.length} />
            )}

            {showUpload && (
                <div style={{ marginBottom: '1rem' }}>
                    <CompanyListUpload onCompaniesParsed={onAddCompanies} />
                </div>
            )}

            <div
                style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.5rem',
                    marginBottom: '1rem',
                    maxHeight: '400px',
                    overflowY: 'auto',
                }}
            >
                {companies.map((company, i) => (
                    <div
                        key={company.url || `${company.name}-${i}`}
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
                            <div style={{ color: 'var(--text-tertiary)', fontSize: '0.8125rem' }}>
                                {company.url || 'No URL — add one to include this company'}
                            </div>
                        </label>
                    </div>
                ))}
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
                <AddCompanyForm existingUrls={companies.map((c) => c.url)} onAdd={onAddCompany} />
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

// Shown for scans with no persisted verdict (e.g. records created before the
// verdict existed) — preserves the original "discovered N" framing.
function FallbackBanner({ count }: { count: number }) {
    return (
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
                aria-hidden="true"
                style={{
                    width: '40px',
                    height: '40px',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--risk-low-bg)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    color: 'var(--risk-low)',
                    fontWeight: 700,
                }}
            >
                ✓
            </div>
            <div>
                <div style={{ fontWeight: 600 }}>Portfolio companies discovered</div>
                <div style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                    Found {count} companies. Review and deselect any you don&apos;t want to analyze.
                </div>
            </div>
        </div>
    )
}
