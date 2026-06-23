'use client'

import { Suspense } from 'react'

import ScanInputPhase from '@/components/scan/ScanInputPhase'
import ScanProgressPhase from '@/components/scan/ScanProgressPhase'
import PortfolioConfirmPhase from '@/components/scan/PortfolioConfirmPhase'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { usePortfolioScanFlow } from '@/lib/hooks/usePortfolioScanFlow'

function NewScanContent() {
    const flow = usePortfolioScanFlow()

    return (
        <div style={{ width: '100%', maxWidth: '680px' }}>
            {/* Header */}
            <div style={{ marginBottom: '2rem' }}>
                <h1 className="page-title">New AI Risk Scan</h1>
                <p style={{ color: 'var(--text-secondary)' }}>
                    Analyze a company or entire PE portfolio for AI-driven risks and opportunities
                </p>
            </div>

            {flow.phase === 'input' && (
                <ScanInputPhase
                    mode={flow.mode}
                    url={flow.url}
                    error={flow.error}
                    onModeChange={flow.setMode}
                    onUrlChange={flow.setUrl}
                    onSubmit={flow.handleSubmit}
                />
            )}

            {(flow.phase === 'analyzing' || flow.phase === 'running') && (
                <ScanProgressPhase
                    phase={flow.phase}
                    progress={flow.progress}
                    progressLabel={flow.progressLabel}
                />
            )}

            {flow.phase === 'portfolio_confirm' && (
                <PortfolioConfirmPhase
                    companies={flow.companies}
                    verdict={flow.verdict}
                    error={flow.error}
                    onCompanyToggle={flow.handleCompanyToggle}
                    onAddCompany={flow.handleAddCompany}
                    onAddCompanies={flow.handleAddCompanies}
                    onSearchDeeper={flow.handleSearchDeeper}
                    onProvideSourceUrl={flow.handleProvideSourceUrl}
                    onConfirm={flow.confirmPortfolio}
                    onReset={flow.resetToInput}
                />
            )}
        </div>
    )
}

export default function NewScanPage() {
    return (
        <Suspense
            fallback={
                <div
                    style={{
                        display: 'flex',
                        minHeight: '50vh',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}
                >
                    <LoadingSpinner size="lg" />
                </div>
            }
        >
            <NewScanContent />
        </Suspense>
    )
}
