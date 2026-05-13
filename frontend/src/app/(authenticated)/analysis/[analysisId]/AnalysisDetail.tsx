'use client'

import { useCallback, useState } from 'react'
import dynamic from 'next/dynamic'

import DocumentUpload from '@/components/DocumentUpload'
import RiskBreakdown from '@/components/RiskBreakdown'
import Sc0redCTABanner from '@/components/Sc0redCTABanner'
import ValueLeverSummary from '@/components/ValueLeverSummary'
import OpportunitiesList from '@/components/OpportunitiesList'
import AnalysisExecutiveStrap from '@/components/analysis/AnalysisExecutiveStrap'
import AnalysisHeader from '@/components/analysis/AnalysisHeader'
import AnalysisOverviewCards from '@/components/analysis/AnalysisOverviewCards'
import AnalysisSection from '@/components/analysis/AnalysisSection'
import EbitdaSection from '@/components/analysis/EbitdaSection'
import FailedAnalysisView from '@/components/analysis/FailedAnalysisView'
import StrategyMapSlot from '@/components/analysis/StrategyMapSlot'
import TopActionsCallout from '@/components/analysis/TopActionsCallout'
import HelpTooltip from '@/components/ui/HelpTooltip'
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
 * Top-to-bottom narrative ordering on this page is governed by the
 * `analysis-detail-narrative` capability spec.
 *
 *   Beat 1   — IDENTITY:    Header → ExecutiveStrap → OverviewCards
 *   Beat 1.5 — DEEP DIVE:   Sc0redCTABanner (advisor consultation)
 *   Beat 2   — SYNTHESIS:   TopActionsCallout
 *   Beat 3   — MONEY:       EbitdaSection → ValueChainDiagram (paired)
 *   Beat 4   — RISK:        RiskBreakdown
 *   Beat 5   — OPPORTUNITY: ValueLever → Opportunities
 *   Beat 6   — STRATEGY:    StrategyMapView + DeepDiveCTA (when present)
 *   Beat 7   — IMPROVE:     DocumentUpload
 *
 * Beat 6 collapses to two states: PRESENT (StrategyMapView +
 * DeepDiveCTA) or ABSENT (slot omitted). The strategy map is now
 * generated inline during the scan pipeline (per
 * ``redesign-strategy-map`` Phase 4), so every newly-completed
 * analysis lands with the map already persisted; legacy analyses that
 * pre-date the inline integration simply hide the slot and rely on
 * "Re-analyze" to regenerate.
 *
 * Section framing (testid + heading + lead) is owned by the shared
 * `AnalysisSection` wrapper. See `analysis-detail-consistency-wrapper` D3.
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
    // Lifted from inside `ValueLeverSummary` so the page-level wrapper
    // can render conditionally — same gating as the other sections that
    // skip rendering entirely on missing data, rather than emitting an
    // empty `<AnalysisSection>` wrapper around a `null` body.
    const hasValueLevers = opportunities.some((o) => o.value_lever)

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
            {/* Beat 1 — IDENTITY.
                Header / strap / overview render testid-only (no `title`
                prop) by intentional design — none of these is a "section
                with a heading-then-body" shape. AnalysisHeader owns the
                page-level `<h1>`; ExecutiveStrap is a one-line band;
                OverviewCards is a paired card row with internal labels.
                See `analysis-detail-consistency-wrapper` D3 for the full
                exempt-section list (7 sections total) and per-section
                rationale. The exempt list is closed for v1; adding a
                new exempt section requires a follow-up spec change. */}
            <AnalysisSection id="header">
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
            </AnalysisSection>

            <AnalysisSection id="strap">
                <AnalysisExecutiveStrap data={data} />
            </AnalysisSection>

            <AnalysisSection id="overview">
                <AnalysisOverviewCards data={data} />
            </AnalysisSection>

            {/* Beat 1.5 — DEEP DIVE.
                sc0red advisor CTA repositioned from after-OpportunitiesList to
                here, with analysis-centric copy ("Dig deeper with a sc0red
                advisor"). Always renders — the banner is a deep-dive
                affordance for the analysis as a whole, not contingent on
                opportunities being non-empty. See `strategy-map-on-demand`
                spec scenario "Banner appears at Beat 4 regardless of
                analysis state". */}
            <AnalysisSection id="sc0red-cta">
                <Sc0redCTABanner
                    contactUrl={getSc0redContactUrl()}
                    analysisId={analysisId}
                    opportunityCount={opportunities.length}
                    activeLeverFilter={toActiveLeverFilter(activeLever)}
                />
            </AnalysisSection>

            {/* Beat 2 — SYNTHESIS (top actions = "so what?") */}
            <AnalysisSection id="top-actions">
                <TopActionsCallout actions={data.topActions ?? []} />
            </AnalysisSection>

            {/* Beat 3 — FINANCIAL PICTURE (EBITDA + Value Chain are paired
                lenses on the same question: where does value sit and how
                is it produced?) */}
            {data.ebitdaTree && (
                <AnalysisSection
                    id="ebitda"
                    title="EBITDA Impact Model"
                    titleAdornment={<HelpTooltip term="ebitda_tree" />}
                >
                    <EbitdaSection ebitdaTree={data.ebitdaTree} opportunities={opportunities} />
                </AnalysisSection>
            )}

            {data.valueChain && data.valueChain.steps.length > 0 && (
                <AnalysisSection id="value-chain" title="Value Chain Analysis">
                    <ValueChainDiagram
                        steps={data.valueChain.steps}
                        opportunities={opportunities}
                        summary={data.valueChain.summary}
                    />
                </AnalysisSection>
            )}

            {/* Beat 5 — RISK + OPPORTUNITY EVIDENCE */}
            <AnalysisSection id="risk-breakdown" title="Risk Breakdown">
                <RiskBreakdown riskScores={riskScores} />
            </AnalysisSection>

            {hasValueLevers && (
                <AnalysisSection
                    id="value-lever"
                    title="Value Impact"
                    titleAdornment={<HelpTooltip term="value_lever" />}
                >
                    <ValueLeverSummary
                        opportunities={opportunities}
                        activeLever={activeLever}
                        onLeverChange={setActiveLever}
                    />
                </AnalysisSection>
            )}

            <AnalysisSection
                id="opportunities"
                title={`AI Opportunities (${opportunities.length})`}
                titleAdornment={<HelpTooltip term="impact_rating" />}
            >
                <OpportunitiesList opportunities={opportunities} activeLever={activeLever} />
            </AnalysisSection>

            {/* Beat 6 — STRATEGIC FRAME. The slot renders the
                ``StrategyMapView`` + ``DeepDiveCTA`` when the map is
                present and renders nothing when it's absent (legacy
                analyses produced before ``redesign-strategy-map``
                Phase 4 inlined map generation into the scan). */}
            <StrategyMapSlot analysisId={analysisId} strategyMap={data.strategyMap} />

            {/* Beat 7 — IMPROVE THIS ANALYSIS. The reanalyze progress bar
                and any reanalyze polling errors render INSIDE the
                DocumentUpload widget rather than as orphan siblings on
                the page. The framing (heading + lead) is owned by the
                AnalysisSection wrapper at the page level so the leaf
                widget stays reusable from FailedAnalysisView with its
                own contextual heading. */}
            <AnalysisSection
                id="document-upload"
                title="Improve This Analysis"
                lead="Upload financial statements, board decks, or product docs and re-analyze to refine this page with the additional context."
            >
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
            </AnalysisSection>
        </>
    )
}
