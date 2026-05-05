'use client'

import { useCallback, useState, type ReactNode } from 'react'
import dynamic from 'next/dynamic'

import DocumentUpload from '@/components/DocumentUpload'
import RiskBreakdown from '@/components/RiskBreakdown'
import Sc0redCTABanner from '@/components/Sc0redCTABanner'
import ValueLeverSummary from '@/components/ValueLeverSummary'
import OpportunitiesList from '@/components/OpportunitiesList'
import AnalysisExecutiveStrap from '@/components/analysis/AnalysisExecutiveStrap'
import AnalysisHeader from '@/components/analysis/AnalysisHeader'
import AnalysisOverviewCards from '@/components/analysis/AnalysisOverviewCards'
import EbitdaSection from '@/components/analysis/EbitdaSection'
import FailedAnalysisView from '@/components/analysis/FailedAnalysisView'
import TopActionsCallout from '@/components/analysis/TopActionsCallout'
import { DeepDiveCTA, StrategyMapView } from '@/components/strategy-map'
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

/**
 * Page-level wrapper for an analysis-detail section. Adds a stable
 * `data-testid` of the form `analysis-section-{name}` so order tests
 * can query sections by DOM order without relying on layout
 * coordinates. Wrapping at the page level keeps section naming a page
 * concern and preserves any existing component-internal testids
 * (e.g., `strategy-map-view`, `strategy-map-cta`) without test churn.
 */
function Section({ id, children }: { id: string; children: ReactNode }) {
    return <div data-testid={`analysis-section-${id}`}>{children}</div>
}

/**
 * Top-to-bottom narrative ordering on this page is governed by the
 * `redesign-analysis-detail-narrative` OpenSpec change. Order rules:
 *
 *   Beat 1 — IDENTITY:    Header → ExecutiveStrap → OverviewCards
 *   Beat 2 — SYNTHESIS:   TopActionsCallout
 *   Beat 3 — STRATEGY:    StrategyMapView (gaps inside) → DeepDiveCTA
 *   Beat 4 — MONEY:       EbitdaSection → ValueChainDiagram (paired)
 *   Beat 5 — RISK + OPP:  RiskBreakdown → ValueLever → Opportunities → Sc0redCTA
 *   Beat 6 — IMPROVE:     DocumentUpload (with progress bar absorbed)
 *
 * The DeepDiveCTA position supersedes PR #239's design.md decision D6
 * (which hoisted it to the top "for visibility") — the new placement
 * fires the CTA at maximum buying intent (right after the strategic
 * gaps it's pitched against) rather than asking for the upsell before
 * any analysis content has been shown.
 */
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
            {/* Beat 1 — IDENTITY */}
            <Section id="header">
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
            </Section>

            <Section id="strap">
                <AnalysisExecutiveStrap data={data} />
            </Section>

            <Section id="overview">
                <AnalysisOverviewCards data={data} />
            </Section>

            {/* Beat 2 — SYNTHESIS (top actions = "so what?") */}
            <Section id="top-actions">
                <TopActionsCallout actions={data.topActions ?? []} />
            </Section>

            {/* Beat 3 — STRATEGIC FRAME */}
            {data.strategyMap ? (
                <Section id="strategy-map">
                    <StrategyMapView strategyMap={data.strategyMap} />
                </Section>
            ) : null}

            {data.strategyMap ? (
                <Section id="deep-dive-cta">
                    <DeepDiveCTA analysisId={analysisId} />
                </Section>
            ) : null}

            {/* Beat 4 — FINANCIAL PICTURE (EBITDA + Value Chain are paired
                lenses on the same question: where does value sit and how
                is it produced?) */}
            {data.ebitdaTree && (
                <Section id="ebitda">
                    <EbitdaSection ebitdaTree={data.ebitdaTree} opportunities={opportunities} />
                </Section>
            )}

            {data.valueChain && data.valueChain.steps.length > 0 && (
                <Section id="value-chain">
                    <ValueChainDiagram
                        steps={data.valueChain.steps}
                        opportunities={opportunities}
                        summary={data.valueChain.summary}
                    />
                </Section>
            )}

            {/* Beat 5 — RISK + OPPORTUNITY EVIDENCE */}
            <Section id="risk-breakdown">
                <RiskBreakdown riskScores={riskScores} />
            </Section>

            <Section id="value-lever">
                <ValueLeverSummary
                    opportunities={opportunities}
                    activeLever={activeLever}
                    onLeverChange={setActiveLever}
                />
            </Section>

            <Section id="opportunities">
                <OpportunitiesList opportunities={opportunities} activeLever={activeLever} />
            </Section>

            {opportunities.length > 0 && (
                <Section id="sc0red-cta">
                    <Sc0redCTABanner
                        contactUrl={getSc0redContactUrl()}
                        analysisId={analysisId}
                        opportunityCount={opportunities.length}
                        activeLeverFilter={toActiveLeverFilter(activeLever)}
                    />
                </Section>
            )}

            {/* Beat 6 — IMPROVE THIS ANALYSIS. The reanalyze progress bar
                and any reanalyze polling errors render INSIDE the
                DocumentUpload widget rather than as orphan siblings on
                the page. The "Improve This Analysis" framing (heading +
                lead) lives at the page level here so the leaf widget
                stays reusable from FailedAnalysisView with its own
                contextual heading. */}
            <Section id="document-upload">
                <h2 className="section-header">Improve This Analysis</h2>
                <p
                    style={{
                        margin: '0 0 1rem',
                        fontSize: '0.875rem',
                        color: 'var(--text-secondary)',
                        lineHeight: 1.6,
                    }}
                >
                    Upload financial statements, board decks, or product docs and re-analyze to refine this
                    page with the additional context.
                </p>
                <DocumentUpload
                    analysisId={analysisId}
                    documents={documents}
                    onDocumentsChange={handleDocumentsChange}
                    onReanalyze={reanalyze.triggerReanalyze}
                    reanalyzing={reanalyze.reanalyzing}
                    reanalysisLabel={reanalyze.reanalysisLabel}
                    reanalysisProgress={reanalyze.reanalysisProgress}
                    documentError={reanalyze.documentError}
                />
            </Section>
        </>
    )
}
