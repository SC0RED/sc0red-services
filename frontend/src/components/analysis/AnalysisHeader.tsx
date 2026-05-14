import Link from 'next/link'

import RiskBadge from '@/components/RiskBadge'
import DeleteAnalysisButton from '@/components/DeleteAnalysisButton'
import ExportPDFButton from '@/components/analysis/ExportPDFButton'
import { prettifyUrl } from '@/lib/utils/url'

interface AnalysisHeaderProps {
    analysisId: string
    companyName: string
    companyUrl?: string
    industry?: string
    tier: string
    scanId?: string
    scanType?: string
    scanSourceUrl?: string
    onExportCsv?: () => void
}

export default function AnalysisHeader({
    analysisId,
    companyName,
    companyUrl,
    industry,
    tier,
    scanId,
    scanType,
    scanSourceUrl,
    onExportCsv,
}: AnalysisHeaderProps) {
    const isPortfolio = scanType === 'portfolio' && Boolean(scanId)
    const scanLabel = scanSourceUrl ? prettifyUrl(scanSourceUrl) : 'portfolio scan'
    return (
        <div
            className="analysis-section-spacing"
            style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                flexWrap: 'wrap',
                gap: '1rem',
            }}
        >
            <div>
                <div
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.25rem',
                        marginBottom: '0.5rem',
                        fontSize: '0.875rem',
                    }}
                >
                    <Link
                        href="/dashboard"
                        style={{
                            color: 'var(--text-tertiary)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                        }}
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
                            <path d="m15 18-6-6 6-6" />
                        </svg>
                        Dashboard
                    </Link>
                    {isPortfolio && (
                        <>
                            <span style={{ color: 'var(--text-tertiary)' }}>/</span>
                            <Link href={`/portfolio/${scanId}`} style={{ color: 'var(--text-tertiary)' }}>
                                {scanLabel}
                            </Link>
                        </>
                    )}
                </div>
                <h1 style={{ fontSize: '1.625rem', fontWeight: 700, marginBottom: '0.375rem' }}>
                    {companyName}
                </h1>
                {isPortfolio && (
                    <div
                        style={{
                            fontSize: '0.875rem',
                            color: 'var(--text-tertiary)',
                            marginBottom: '0.5rem',
                        }}
                    >
                        Part of:{' '}
                        <Link
                            href={`/portfolio/${scanId}`}
                            style={{
                                color: 'var(--text-secondary)',
                                textDecoration: 'underline',
                                textDecorationStyle: 'dotted',
                                textUnderlineOffset: '2px',
                            }}
                        >
                            {scanLabel}
                        </Link>
                    </div>
                )}
                <div
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.75rem',
                        flexWrap: 'wrap',
                    }}
                >
                    <RiskBadge tier={tier} />
                    {industry && <span className="badge badge-neutral">{industry}</span>}
                    {companyUrl && (
                        <a
                            href={companyUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                                color: 'var(--text-tertiary)',
                                fontSize: '0.875rem',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.25rem',
                            }}
                        >
                            <svg
                                width="13"
                                height="13"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            >
                                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                                <polyline points="15 3 21 3 21 9" />
                                <line x1="10" y1="14" x2="21" y2="3" />
                            </svg>
                            {companyUrl}
                        </a>
                    )}
                </div>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <ExportPDFButton analysisId={analysisId} />
                {onExportCsv && (
                    <button type="button" onClick={onExportCsv} className="btn btn-secondary">
                        <svg
                            width="15"
                            height="15"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        >
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                            <polyline points="14 2 14 8 20 8" />
                            <line x1="16" y1="13" x2="8" y2="13" />
                            <line x1="16" y1="17" x2="8" y2="17" />
                        </svg>
                        Export CSV
                    </button>
                )}
                <DeleteAnalysisButton
                    analysisId={analysisId}
                    companyName={companyName}
                    variant="button"
                    redirectTo="/analyses"
                />
            </div>
        </div>
    )
}
