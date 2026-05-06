import AnalysisSection from '@/components/analysis/AnalysisSection'
import StrategyMapCTA from '@/components/analysis/StrategyMapCTA'
import StrategyMapGeneratingPlaceholder from '@/components/analysis/StrategyMapGeneratingPlaceholder'
import { DeepDiveCTA, StrategyMapView } from '@/components/strategy-map'
import type { StrategyMap } from '@/lib/types/api'

interface StrategyMapSlotProps {
    analysisId: string
    strategyMap?: StrategyMap | null
    isGenerating: boolean
    generationError: string | null
    onGenerationStarted: () => void
}

/**
 * The Beat-6 strategy-map slot. Three mutually-exclusive states (per the
 * `strategy-map-on-demand` spec scenario "Strategy-map slot renders
 * three distinct states"):
 *
 *   1. PRESENT     → `StrategyMapView` + `DeepDiveCTA`
 *   2. GENERATING  → placeholder + status message
 *   3. ABSENT      → on-demand CTA
 *
 * The CTA does NOT render while a generation is in flight — otherwise
 * users could enqueue duplicate jobs. Extracted from `AnalysisDetail`
 * to keep the parent component under the 360-line frontend file-size
 * limit (CLAUDE.md). Each branch wraps in `AnalysisSection` with the
 * appropriate testid so the page-level beat-order tests still see the
 * `analysis-section-strategy-map` (and, when present, the
 * `analysis-section-deep-dive-cta`) wrappers.
 */
export default function StrategyMapSlot({
    analysisId,
    strategyMap,
    isGenerating,
    generationError,
    onGenerationStarted,
}: StrategyMapSlotProps) {
    if (strategyMap) {
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

    if (isGenerating) {
        return (
            <AnalysisSection id="strategy-map">
                <StrategyMapGeneratingPlaceholder />
            </AnalysisSection>
        )
    }

    return (
        <AnalysisSection id="strategy-map">
            <StrategyMapCTA
                analysisId={analysisId}
                failureMessage={generationError}
                onGenerationStarted={onGenerationStarted}
            />
        </AnalysisSection>
    )
}
