import { useState } from 'react'

import AddCompanyForm from '@/components/scan/AddCompanyForm'
import CompanyListUpload from '@/components/scan/CompanyListUpload'
import DiscoveryVerdictBanner from '@/components/scan/DiscoveryVerdictBanner'
import ProvideSourceUrlForm from '@/components/scan/ProvideSourceUrlForm'
import type { Company, CompanySource, DiscoveryVerdict } from '@/lib/types/scan'

interface PortfolioConfirmPhaseProps {
    companies: Company[]
    verdict?: DiscoveryVerdict | null
    /** Error from a failed confirm/deepen attempt that returned the customer to
     *  this screen — surfaced inline so a failure isn't silent. */
    error?: string
    onCompanyToggle: (index: number, selected: boolean) => void
    onAddCompany: (name: string, url: string) => void
    /** Bulk-merge parsed uploads into the list; returns how many were newly
     *  added (the rest were dedup hits), so the uploader can report accurately. */
    onAddCompanies: (companies: Array<{ name: string; url: string }>) => number
    onSearchDeeper: () => void
    /** Fetch a customer-provided page server-side and merge its companies in. */
    onProvideSourceUrl: (url: string) => void
    onConfirm: () => void
    onReset: () => void
}

export default function PortfolioConfirmPhase({
    companies,
    verdict,
    error,
    onCompanyToggle,
    onAddCompany,
    onAddCompanies,
    onSearchDeeper,
    onProvideSourceUrl,
    onConfirm,
    onReset,
}: PortfolioConfirmPhaseProps) {
    const selectedCount = companies.filter((c) => c.selected).length
    const [showUpload, setShowUpload] = useState(false)

    return (
        <div>
            {error && (
                <div
                    role="alert"
                    className="card"
                    style={{
                        padding: '0.75rem 1rem',
                        marginBottom: '1rem',
                        color: 'var(--risk-high)',
                        fontSize: '0.875rem',
                    }}
                >
                    {error}
                </div>
            )}
            {verdict ? (
                <DiscoveryVerdictBanner
                    verdict={verdict}
                    currentCount={companies.length}
                    onUploadList={() => setShowUpload((open) => !open)}
                    onSearchDeeper={onSearchDeeper}
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
                            <div
                                style={{
                                    fontWeight: 500,
                                    fontSize: '0.9rem',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem',
                                    flexWrap: 'wrap',
                                }}
                            >
                                {company.name}
                                <SourceBadge source={company.source} />
                            </div>
                            <div style={{ color: 'var(--text-tertiary)', fontSize: '0.8125rem' }}>
                                {company.url || 'No URL — add one to include this company'}
                            </div>
                        </label>
                    </div>
                ))}
            </div>

            <div style={{ marginBottom: '0.5rem' }}>
                <AddCompanyForm existingUrls={companies.map((c) => c.url)} onAdd={onAddCompany} />
            </div>
            <div style={{ marginBottom: '1.5rem' }}>
                <ProvideSourceUrlForm onProvideSourceUrl={onProvideSourceUrl} />
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

// Per-row provenance marker: web-search rows are flagged best-effort ("verify"),
// site/provided-url rows are marked reliable. Upload/manual (untagged) get no
// badge — they're customer-supplied and trusted by default.
function SourceBadge({ source }: { source?: CompanySource }) {
    if (source === 'web_search') {
        return (
            <span
                style={{
                    fontSize: '0.6875rem',
                    color: 'var(--risk-medium)',
                    border: '1px solid var(--risk-medium)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '0 0.375rem',
                    whiteSpace: 'nowrap',
                }}
            >
                via web search — verify
            </span>
        )
    }
    const reliableLabel: Partial<Record<CompanySource, string>> = {
        site: 'from firm’s site',
        provided_url: 'from your source',
        upload: 'from your list',
    }
    const label = source && reliableLabel[source]
    if (label) {
        return (
            <span style={{ fontSize: '0.6875rem', color: 'var(--risk-low)', whiteSpace: 'nowrap' }}>
                ✓ {label}
            </span>
        )
    }
    return null
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
