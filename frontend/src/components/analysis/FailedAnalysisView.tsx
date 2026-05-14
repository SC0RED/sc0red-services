'use client'

import DocumentUpload from '@/components/DocumentUpload'
import { LoadingSpinner } from '@/components/ui'
import type { DocumentInfo } from '@/lib/types/api'

interface FailedAnalysisViewProps {
    analysisId: string
    companyName: string
    companyUrl?: string
    error: string
    scanId?: string
    scanType?: string
    documents: DocumentInfo[]
    documentError: string | null
    reanalyzing: boolean
    reanalysisProgress: number
    reanalysisLabel: string
    onRetry: () => void
    onDocumentsChange: () => void
}

export default function FailedAnalysisView({
    analysisId,
    companyName,
    companyUrl,
    error,
    scanId,
    scanType,
    documents,
    documentError,
    reanalyzing,
    reanalysisProgress,
    reanalysisLabel,
    onRetry,
    onDocumentsChange,
}: FailedAnalysisViewProps) {
    const isPortfolio = scanType === 'portfolio' && Boolean(scanId)
    return (
        <div style={{ maxWidth: '680px' }}>
            {isPortfolio && (
                <a
                    href={`/portfolio/${scanId}`}
                    style={{
                        display: 'inline-block',
                        color: 'var(--text-secondary)',
                        fontSize: '0.875rem',
                        marginBottom: '1rem',
                    }}
                >
                    &larr; Back to Portfolio
                </a>
            )}
            <div className="card" style={{ padding: '2rem' }}>
                <div
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        marginBottom: '1.5rem',
                    }}
                >
                    <span style={{ fontSize: '1.125rem' }}>&#9888;</span>
                    <h1 style={{ fontSize: '1.125rem', fontWeight: 700, margin: 0 }}>Analysis Failed</h1>
                </div>

                <div style={{ marginBottom: '1rem' }}>
                    <div style={{ fontWeight: 600, fontSize: '1rem', marginBottom: '0.25rem' }}>
                        {companyName || 'Unknown Company'}
                    </div>
                    {companyUrl && (
                        <a
                            href={companyUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ fontSize: '0.875rem', color: 'var(--accent-blue)' }}
                        >
                            {companyUrl}
                        </a>
                    )}
                </div>

                <div
                    style={{
                        padding: '0.75rem 1rem',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        borderRadius: '6px',
                        fontSize: '0.875rem',
                        color: 'var(--risk-critical)',
                        marginBottom: '1.5rem',
                    }}
                >
                    {error}
                </div>

                <div style={{ marginBottom: '1.5rem' }}>
                    <h3
                        style={{
                            fontSize: '0.875rem',
                            fontWeight: 600,
                            marginBottom: '0.75rem',
                        }}
                    >
                        Upload supporting documents (optional)
                    </h3>
                    <DocumentUpload
                        analysisId={analysisId}
                        documents={documents}
                        onDocumentsChange={onDocumentsChange}
                    />
                </div>

                {documentError && (
                    <div
                        role="alert"
                        className="alert-error"
                        style={{
                            fontSize: '0.875rem',
                            color: 'var(--risk-critical)',
                            marginBottom: '1rem',
                        }}
                    >
                        {documentError}
                    </div>
                )}

                {reanalyzing ? (
                    <div style={{ textAlign: 'center', padding: '1rem 0' }}>
                        <LoadingSpinner />
                        <div
                            style={{
                                fontSize: '0.875rem',
                                color: 'var(--text-secondary)',
                                marginTop: '0.5rem',
                            }}
                        >
                            {reanalysisLabel || 'Retrying analysis...'}
                            {reanalysisProgress > 0 && ` (${reanalysisProgress}%)`}
                        </div>
                    </div>
                ) : (
                    <button onClick={onRetry} className="btn-primary" style={{ width: '100%' }}>
                        Retry Analysis
                    </button>
                )}
            </div>
        </div>
    )
}
