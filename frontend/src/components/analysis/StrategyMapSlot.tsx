import AnalysisSection from '@/components/analysis/AnalysisSection'
import { DeepDiveCTA, StrategyMapView } from '@/components/strategy-map'
import type { StrategyMap } from '@/lib/types/api'

interface StrategyMapSlotProps {
    analysisId: string
    strategyMap?: StrategyMap | null
}

/**
 * The Beat-6 strategy-map slot.
 *
 * Strategy maps are now generated inline during the scan pipeline
 * (per ``redesign-strategy-map`` Phase 4) — when the user lands on
 * the analysis detail page, the map is either already persisted
 * (rendered with the ``DeepDiveCTA`` follow-up) or absent (legacy
 * analyses produced before Phase 4; the slot is omitted entirely).
 * There is no longer an in-flight "generating…" state, an on-demand
 * CTA, or a "regenerate" affordance — re-analysing the company
 * regenerates the map as part of the scan.
 */
export default function StrategyMapSlot({ analysisId, strategyMap }: StrategyMapSlotProps) {
    if (!strategyMap) {
        return null
    }
    return (
        <>
            <AnalysisSection id="strategy-map">
                <StrategyMapView strategyMap={strategyMap} />
            </AnalysisSection>
            <AnalysisSection id="deep-dive-cta">
                <DeepDiveCTA analysisId={analysisId} />
            </AnalysisSection>
        </>
    )
}
