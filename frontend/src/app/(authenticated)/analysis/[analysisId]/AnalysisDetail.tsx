'use client'

import { useCallback, useState } from 'react'
import dynamic from 'next/dynamic'

import DocumentUpload from '@/components/DocumentUpload'
import RiskBreakdown from '@/components/RiskBreakdown'
import Sc0redCTABanner from '@/components/Sc0redCTABanner'
import ValueLeverSummary from '@/components/ValueLeverSummary'
import OpportunitiesList from '@/components/OpportunitiesList'
import AnalysisHeader from '@/components/analysis/AnalysisHeader'
import AnalysisOverviewCards from '@/components/analysis/AnalysisOverviewCards'
import EbitdaSection from '@/components/analysis/EbitdaSection'
import FailedAnalysisView from '@/components/analysis/FailedAnalysisView'
import TopActionsCallout from '@/components/analysis/TopActionsCallout'
import { LoadingSpinner } from '@/components/ui'
import { getSc0redContactUrl } from '@/lib/config'
import { useReanalyze } from '@/lib/hooks/useReanalyze'
import { exportAnalysisDetailCsv } from '@/lib/utils/csvExport'
import { getRiskTier } from '@/lib/utils/riskUtils'
import type { AnalysisData, DocumentInfo } from '@/lib/types/api'
import type { ActiveLeverFilter } from '@/lib/types/analytics'

const ValueChainDiagram = dynamic(() => import('@/components/ValueChainDiagram'), {
    loading: () => (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
            <LoadingSpinner />
        </div>
    ),
    ssr: false,
})

/**
 * Map the screen-level lever filter ("All" / "Revenue Side" / "Cost
 * Side" / "Both") down to the analytics enum the CTA banner emits.
 * Only the two named levers are tracked as filters; "All", "Both",
 * or anything else collapses to null. Mirrors the previous helper that
 * lived inline in `OpportunitiesList` before the CTA was lifted to
 * this parent surface.
 */
function toActiveLeverFilter(activeLever: string): ActiveLeverFilter | null {
    if (activeLever === 'Revenue Side' || activeLever === 'Cost Side') {
        return activeLever
    }
    return null
}

export default function AnalysisDetail({ data, analysisId }: { data: AnalysisData; analysisId: string }) {
    const [activeLever, setActiveLever] = useState<string>('All')
    const [documents, setDocuments] = useState<DocumentInfo[]>(data.documents ?? [])

    const reanalyze = useReanalyze({ analysisId, analyzedAt: data.analyzedAt })

    const handleDocumentsChange = useCallback(async () => {
        reanalyze.clearError()
        try {
            const response = await fetch(`/api/analysis/${analysisId}`)
            if (!response.ok) throw new Error('Failed to refresh documents')
            const updated = (await response.json()) as AnalysisData
            setDocuments(updated.documents ?? [])
        } catch (error: unknown) {
            const message = error instanceof Error ? error.message : 'Failed to refresh documents'
            reanalyze.setDocumentError(message)
        }
    }, [analysisId, reanalyze])

    const riskScores = data.riskScores ?? []
    const opportunities = data.opportunities ?? []
    const tier = data.riskTier || getRiskTier(data.overallRiskScore ?? 0)

    // Failed analysis — show error + retry UI instead of the full analysis.
    if (data.error && !data.analyzedAt) {
        return (
            <FailedAnalysisView
                analysisId={analysisId}
                companyName={data.companyName}
                companyUrl={data.companyUrl}
                error={data.error}
                scanId={data.scanId}
                scanType={data.scanType}
                documents={documents}
                documentError={reanalyze.documentError}
                reanalyzing={reanalyze.reanalyzing}
                reanalysisProgress={reanalyze.reanalysisProgress}
                reanalysisLabel={reanalyze.reanalysisLabel}
                onRetry={reanalyze.triggerReanalyze}
                onDocumentsChange={handleDocumentsChange}
            />
        )
    }

    return (
        <>
            <AnalysisHeader
                analysisId={analysisId}
                companyName={data.companyName}
                companyUrl={data.companyUrl}
                industry={data.industry}
                tier={tier}
                scanId={data.scanId}
                scanType={data.scanType}
                scanSourceUrl={data.scanSourceUrl}
                onExportCsv={() => exportAnalysisDetailCsv(data)}
            />

            <AnalysisOverviewCards data={data} />

            <TopActionsCallout actions={data.topActions ?? []} />

            <RiskBreakdown riskScores={riskScores} />

            <ValueLeverSummary
                opportunities={opportunities}
                activeLever={activeLever}
                onLeverChange={setActiveLever}
            />

            <OpportunitiesList opportunities={opportunities} activeLever={activeLever} />

            {opportunities.length > 0 && (
                <Sc0redCTABanner
                    contactUrl={getSc0redContactUrl()}
                    analysisId={analysisId}
                    opportunityCount={opportunities.length}
                    activeLeverFilter={toActiveLeverFilter(activeLever)}
                />
            )}

            {data.valueChain && data.valueChain.steps.length > 0 && (
                <ValueChainDiagram
                    steps={data.valueChain.steps}
                    opportunities={opportunities}
                    summary={data.valueChain.summary}
                />
            )}

            {reanalyze.reanalyzing && (
                <div
                    className="card"
                    style={{ padding: '1.5rem', marginBottom: '1.5rem', textAlign: 'center' }}
                >
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                        Re-analyzing with documents...
                    </h3>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1rem' }}>
                        {reanalyze.reanalysisLabel || 'Starting pipeline...'}
                    </p>
                    <div className="progress-bar" style={{ maxWidth: '360px', margin: '0 auto' }}>
                        <div
                            className="progress-fill"
                            style={{ width: `${reanalyze.reanalysisProgress}%` }}
                        />
                    </div>
                    <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
                        {reanalyze.reanalysisProgress}% complete
                    </div>
                </div>
            )}

            {reanalyze.documentError && (
                <div className="alert-error" style={{ marginBottom: '1rem' }}>
                    {reanalyze.documentError}
                </div>
            )}
            <DocumentUpload
                analysisId={analysisId}
                documents={documents}
                onDocumentsChange={handleDocumentsChange}
                onReanalyze={reanalyze.triggerReanalyze}
                reanalyzing={reanalyze.reanalyzing}
            />

            {data.ebitdaTree && <EbitdaSection ebitdaTree={data.ebitdaTree} opportunities={opportunities} />}
        </>
    )
}
