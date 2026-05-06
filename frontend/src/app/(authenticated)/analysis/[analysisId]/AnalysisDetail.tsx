'use client'

import { useCallback, useEffect, useState } from 'react'
import dynamic from 'next/dynamic'
import { useRouter } from 'next/navigation'

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
import { useStrategyMapSubscription } from '@/lib/hooks/useStrategyMapSubscription'
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
 * `analysis-detail-narrative` capability spec. Order rules (post
 * `strategy-map-on-demand` Phase B):
 *
 *   Beat 1   — IDENTITY:    Header → ExecutiveStrap → OverviewCards
 *   Beat 1.5 — DEEP DIVE:   Sc0redCTABanner (advisor consultation)
 *   Beat 2   — SYNTHESIS:   TopActionsCallout
 *   Beat 3   — MONEY:       EbitdaSection → ValueChainDiagram (paired)
 *   Beat 4   — RISK:        RiskBreakdown
 *   Beat 5   — OPPORTUNITY: ValueLever → Opportunities
 *   Beat 6   — STRATEGY:    StrategyMapCTA / generating / StrategyMapView
 *                           + DeepDiveCTA (only when map is present)
 *   Beat 7   — IMPROVE:     DocumentUpload
 *
 * The strategy-map slot has three states (per the strategy-map-on-demand
 * spec): CTA when absent and not generating, generating placeholder while
 * the worker is running, full StrategyMapView + DeepDiveCTA when the map
 * is persisted. The states are mutually exclusive — the CTA does NOT
 * render while a generation is in flight (otherwise users could enqueue
 * duplicate jobs).
 *
 * Section framing (testid + heading + lead) is owned by the shared
 * `AnalysisSection` wrapper. Sections that have a heading pass it via
 * `title`; sections that don't (StrategyMapView, Sc0redCTABanner,
 * DeepDiveCTA, TopActionsCallout, AnalysisOverviewCards,
 * AnalysisExecutiveStrap, AnalysisHeader, StrategyMapCTA,
 * StrategyMapGeneratingPlaceholder) wrap with no `title` — testid-only
 * render. See `analysis-detail-consistency-wrapper` D3.
 */
export default function AnalysisDetail({ data, analysisId }: { data: AnalysisData; analysisId: string }) {
    const [activeLever, setActiveLever] = useState<string>('All')
    const [documents, setDocuments] = useState<DocumentInfo[]>(data.documents ?? [])
    // Local override of the API-served generation state. Lets the CTA
    // optimistically flip to "generating" the moment the user clicks,
    // before the next /api/analysis/{id} fetch confirms the server-side
    // state. Cleared on AppSync complete/failed events.
    const [localGenerating, setLocalGenerating] = useState<boolean>(false)
    const [generationError, setGenerationError] = useState<string | null>(null)

    const reanalyze = useReanalyze({ analysisId, analyzedAt: data.analyzedAt })
    const { start: startStrategyMapSubscription, stop: stopStrategyMapSubscription } =
        useStrategyMapSubscription()
    const router = useRouter()

    // The strategy-map slot derives its state from three signals:
    // (a) the persisted map on `data` (== present), (b) the API-served
    // `strategyMapGenerationState` on `data` (== generating), and
    // (c) the `localGenerating` override (== just-clicked, not yet
    // round-tripped). Any of (b) or (c) flips to generating; the AppSync
    // events flip back.
    const isGenerating = localGenerating || data.strategyMapGenerationState === 'generating'

    // Re-fetch the SSR-rendered analysis page so the persisted map (or
    // refreshed `strategyMapGenerationState`) is reflected. `router.refresh()`
    // re-runs the server component without dropping ephemeral client state
    // — matches the pattern used by `useReanalyze`.
    const refetchAnalysis = useCallback(() => {
        router.refresh()
    }, [router])

    // Subscribe to AppSync when the slot is in the generating state.
    // Dep array uses the destructured `start`/`stop` callbacks from the
    // hook (both `useCallback`-stable across renders) rather than the
    // hook return object — wrapping them in an object literal would be a
    // new reference on every render and would tear down the subscription
    // on every parent re-render.
    useEffect(() => {
        if (!isGenerating || !data.scanId) return

        void startStrategyMapSubscription({
            analysisId,
            scanId: data.scanId,
            onComplete: () => {
                setLocalGenerating(false)
                setGenerationError(null)
                refetchAnalysis()
            },
            onFailed: () => {
                setLocalGenerating(false)
                setGenerationError("We couldn't generate your strategy map. Click Generate to try again.")
            },
            onTimeout: () => {
                // The 90s client-side fallback. The worker may have
                // completed and the AppSync event was lost — refetch
                // checks the persisted state. If the server still says
                // `generating`, the next render re-enters this effect
                // and re-subscribes.
                refetchAnalysis()
            },
        })

        return () => stopStrategyMapSubscription()
    }, [
        isGenerating,
        analysisId,
        data.scanId,
        startStrategyMapSubscription,
        stopStrategyMapSubscription,
        refetchAnalysis,
    ])

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

            {/* Beat 6 — STRATEGIC FRAME (on-demand). See `StrategyMapSlot`
                for the three-state branching (present / generating /
                absent). Extracted to a sibling component so this
                top-level page stays under the 360-line file-size limit. */}
            <StrategyMapSlot
                analysisId={analysisId}
                strategyMap={data.strategyMap}
                isGenerating={isGenerating}
                generationError={generationError}
                onGenerationStarted={() => {
                    setLocalGenerating(true)
                    setGenerationError(null)
                }}
            />

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
