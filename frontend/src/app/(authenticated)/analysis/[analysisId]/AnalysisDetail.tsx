'use client'

import { useCallback, useState } from 'react'
import dynamic from 'next/dynamic'

import DocumentUpload from '@/components/DocumentUpload'
import RiskBreakdown from '@/components/RiskBreakdown'
import ValueLeverSummary from '@/components/ValueLeverSummary'
import OpportunitiesList from '@/components/OpportunitiesList'
import QuickWinsMatrix from '@/components/analysis/QuickWinsMatrix'
import AnalysisExecutiveStrap from '@/components/analysis/AnalysisExecutiveStrap'
import AnalysisHeader from '@/components/analysis/AnalysisHeader'
import AnalysisOverviewCards from '@/components/analysis/AnalysisOverviewCards'
import AnalysisSection from '@/components/analysis/AnalysisSection'
import EbitdaSection from '@/components/analysis/EbitdaSection'
import FailedAnalysisView from '@/components/analysis/FailedAnalysisView'
import StrategyMapSlot from '@/components/analysis/StrategyMapSlot'
import TopActionsCallout from '@/components/analysis/TopActionsCallout'
import DeepDiveCTA from '@/components/strategy-map/DeepDiveCTA'
import StrategyMapDetailsSection from '@/components/strategy-map/StrategyMapDetailsSection'
import HelpTooltip from '@/components/ui/HelpTooltip'
import { OpportunityHoverProvider } from '@/lib/hooks/useOpportunityHover'
import { LoadingSpinner } from '@/components/ui'
import { useReanalyze } from '@/lib/hooks/useReanalyze'
import { exportAnalysisDetailCsv } from '@/lib/utils/csvExport'
import { getRiskTier } from '@/lib/utils/riskUtils'
import type { AnalysisData, DocumentInfo } from '@/lib/types/api'

const ValueChainDiagram = dynamic(() => import('@/components/ValueChainDiagram'), {
    loading: () => (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
            <LoadingSpinner />
        </div>
    ),
    ssr: false,
})

/**
 * Top-to-bottom narrative ordering on this page (per
 * ``redesign-strategy-map`` Phase 5):
 *
 *   Beat 1 — IDENTITY:    Header → ExecutiveStrap → OverviewCards
 *   Beat 2 — SYNTHESIS:   TopActionsCallout (top-3 immediate actions)
 *   Beat 3 — STRATEGY:    StrategyMapView + DeepDiveCTA (when present)
 *   Beat 4 — MONEY:       EbitdaSection → ValueChainDiagram (paired)
 *   Beat 5 — RISK:        RiskBreakdown
 *   Beat 6 — OPPORTUNITY: ValueLever → Opportunities
 *   Beat 7 — IMPROVE:     DocumentUpload
 *
 * The strategy map sits IMMEDIATELY after the top-3 immediate actions
 * so the visual story is "here's what to do → here's the strategic
 * frame that makes it coherent → here's the supporting evidence
 * (money / risk / opportunities)". Previously the map lived at the
 * very bottom (Beat 6) where users rarely scrolled to it.
 *
 * The standalone ``Sc0redCTABanner`` ("Dig deeper with a sc0red
 * advisor") that previously sat at Beat 1.5 was deleted in Phase 5 —
 * the ``DeepDiveCTA`` rendered alongside the strategy map ("Want a
 * deeper analysis?") now sits high enough on the page to serve the
 * same conversion role without a second banner.
 *
 * The Beat-3 strategy-map slot collapses to two states: PRESENT
 * (``StrategyMapView`` + ``DeepDiveCTA``) or ABSENT (slot omitted).
 * Maps are generated inline during the scan pipeline (Phase 4); the
 * absent case only applies to legacy analyses produced before that
 * change, which can recover via "Re-analyze".
 *
 * Section framing (testid + heading + lead) is owned by the shared
 * ``AnalysisSection`` wrapper. See ``analysis-detail-consistency-wrapper`` D3.
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
    // Gate the relocated Value Proposition + Strategic Priorities
    // ExpandableSection at the call site so the AnalysisSection wrapper
    // doesn't render an empty heading when both fields are absent (the
    // component's internal null-return would still leave an orphan
    // wrapper otherwise). Matches the spec's "renders when the strategy
    // map is present AND has at least one of VP or priorities" rule.
    const hasStrategyDetails =
        !!data.strategyMap &&
        (!!data.strategyMap.valueProposition.primary || data.strategyMap.strategicPriorities.length > 0)

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
        // P5 (redesign-analysis-visuals): wrap the analysis body in the
        // hover provider so EBITDA leaves, value-chain steps, the
        // strategy-map cells (P6), and the Quick Wins matrix dots (P7)
        // can all dispatch highlight events that the OpportunitiesList
        // cards below subscribe to (and vice versa).
        <OpportunityHoverProvider>
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

            {/* Beat 2 — SYNTHESIS (top actions = "so what?") */}
            <AnalysisSection id="top-actions">
                <TopActionsCallout actions={data.topActions ?? []} />
            </AnalysisSection>

            {/* Beat 3 — STRATEGIC FRAME. Sits directly under the top-3
                immediate actions so the user sees the strategic story
                (Vision / Mission / Value Proposition / Strategic
                Priorities + the perspectives map) before the
                supporting evidence. The ``DeepDiveCTA`` rendered by
                the slot doubles as the page-level deep-dive
                affordance (the standalone ``Sc0redCTABanner`` at
                Beat 1.5 was deleted in Phase 5 as redundant).
                Renders nothing when no strategy map is persisted
                — legacy analyses produced before
                ``redesign-strategy-map`` Phase 4 inlined map
                generation into the scan. */}
            <StrategyMapSlot
                analysisId={analysisId}
                strategyMap={data.strategyMap}
                opportunities={opportunities}
            />

            {/* Value Proposition + Strategic Priorities — relocated
                here from the strategy-map header by Phase 12 of
                redesign-analysis-visuals (Diagnostic Tool Feedback #4:
                "at the top here I would just have mission and vision").
                Collapsed by default; the section renders nothing when
                both fields are absent. Gating is internal to the
                component to keep this call site simple. */}
            {hasStrategyDetails && data.strategyMap ? (
                <AnalysisSection id="value-proposition-priorities">
                    <StrategyMapDetailsSection
                        valueProposition={data.strategyMap.valueProposition}
                        strategicPriorities={data.strategyMap.strategicPriorities}
                    />
                </AnalysisSection>
            ) : null}

            {/* Beat 4 — FINANCIAL PICTURE (EBITDA + Value Chain are paired
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

            {/* Beat 5 — RISK + Beat 6 — OPPORTUNITY EVIDENCE */}
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

            {/* Quick Wins 2×2 matrix — Phase 7 of redesign-analysis-visuals.
                Sits immediately after the OpportunitiesList so the reader
                sees the same opportunities plotted by impact × timeline
                right after they read the cards. Clicking a dot pulses +
                scrolls the matching opportunity card into view via the
                P5 hover provider. Gated on opportunities.length >= 1 to
                match the "no orphan visualisations on sparse reports"
                rule the other sections use. */}
            {opportunities.length >= 1 && (
                <AnalysisSection id="quick-wins-matrix" title="Quick Wins Matrix">
                    <QuickWinsMatrix opportunities={opportunities} />
                </AnalysisSection>
            )}

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

            {/*
             * End-of-analysis Contact-us CTA — Diagnostic Tool Feedback #8.
             * Zack: "at the end of this analysis I would duplicate the
             * 'contact us' bar you have in the middle of the analysis as
             * well, since ideally when they get to the end they'll want to
             * get in touch."
             *
             * Renders on EVERY successful analysis page (Phase 11 of
             * ``redesign-analysis-visuals`` removed the prior
             * ``opportunities.length > 0`` gate). The CTA's purpose is
             * "the user reached the end of the page; offer them the next
             * step" — that purpose holds whether or not the AI surfaced
             * specific opportunities. Gating on opportunity count would
             * leave sparse reports without a contact path, the opposite of
             * what we want.
             *
             * The ``placement="analysis-end"`` prop switches the analytics
             * event name to ``sc0red_cta_rendered_analysis_end`` and the
             * outbound URL's ``?source=analysis-end``. Funnel queries can
             * now attribute impressions and clicks to the right surface
             * (the prior implementation double-counted the strategy-map
             * funnel by firing the ``_strategy_map`` events here).
             */}
            <AnalysisSection id="deep-dive-cta-end">
                <DeepDiveCTA analysisId={analysisId} placement="analysis-end" />
            </AnalysisSection>
        </OpportunityHoverProvider>
    )
}
