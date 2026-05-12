import { RISK_CATEGORIES } from '@/lib/utils/riskUtils'
import type { AnalysisData, EbitdaTree, RiskScore } from '@/lib/types/api'

import type { OpportunityWithIndex } from './sortOpportunities'

/**
 * View-model for the executive summary page in the printed PDF.
 *
 * Derived from existing `AnalysisData` fields — no schema change. The
 * shape is what the `PrintExecutiveSummary` component consumes; the
 * derivation logic lives here so the same view can be unit-tested
 * without rendering React.
 *
 * The whole summary is omitted from the PDF when both `riskScores` and
 * `opportunities` are empty (the helper returns `null`). EBITDA-uplift
 * and risk-driver lines individually drop to `null` when their source
 * data is missing — `PrintExecutiveSummary` skips them.
 */
export interface DerivedSummary {
    riskDrivers: RiskDriverLine[]
    opportunityHighlights: OpportunityHighlightLine[]
    ebitdaUplift: EbitdaUpliftBar | null
}

export interface RiskDriverLine {
    category: string
    /** Display name from RISK_CATEGORIES, or the raw id when unknown. */
    label: string
    score: number
    /** First sentence of the rationale; empty string when absent. */
    rationaleFirstSentence: string
}

export interface OpportunityHighlightLine {
    /** 1-based printed position used for cross-references in the PDF. */
    printedIndex: number
    title: string
    impactRating: 'High' | 'Medium' | 'Low'
    timeline: string
    /** May be undefined when the upstream model didn't populate it. */
    investmentRange: string | undefined
}

export interface EbitdaUpliftBar {
    /** Display string from `revenueEstimate` — already formatted upstream. */
    revenueEstimate: string | undefined
    /** Display string from `ebitdaEstimate`. */
    ebitdaEstimate: string | undefined
    /** Pulled from `businessModelSummary` — one-line gloss above the bar. */
    summary: string | undefined
}

const SUMMARY_RISK_LIMIT = 3
const SUMMARY_OPPORTUNITY_LIMIT = 3

/**
 * Derive the executive-summary view model from an analysis.
 *
 * Returns `null` when the analysis has neither risk scores nor
 * opportunities — the section is omitted entirely in that case (no
 * empty page in the PDF). Otherwise returns a populated structure;
 * downstream components individually skip empty sub-sections.
 *
 * The `sortedOpportunities` parameter MUST be the same sorted array
 * threaded through the rest of the print components so the
 * `printedIndex` references align across sections.
 */
export function deriveSummary(
    analysis: AnalysisData,
    sortedOpportunities: OpportunityWithIndex[]
): DerivedSummary | null {
    const riskScores = analysis.riskScores ?? []
    const hasOpportunities = sortedOpportunities.length > 0
    const hasRisks = riskScores.length > 0

    if (!hasRisks && !hasOpportunities) {
        return null
    }

    return {
        riskDrivers: pickTopRisks(riskScores),
        opportunityHighlights: pickTopOpportunities(sortedOpportunities),
        ebitdaUplift: deriveEbitdaUplift(analysis.ebitdaTree),
    }
}

function pickTopRisks(riskScores: RiskScore[]): RiskDriverLine[] {
    return [...riskScores]
        .sort((a, b) => b.score - a.score)
        .slice(0, SUMMARY_RISK_LIMIT)
        .map((rs) => ({
            category: rs.category,
            label: RISK_CATEGORIES.find((c) => c.id === rs.category)?.name ?? rs.category,
            score: rs.score,
            rationaleFirstSentence: getFirstSentence(rs.rationale),
        }))
}

function pickTopOpportunities(sorted: OpportunityWithIndex[]): OpportunityHighlightLine[] {
    return sorted.slice(0, SUMMARY_OPPORTUNITY_LIMIT).map(({ opportunity, printedIndex }) => ({
        printedIndex,
        title: opportunity.title,
        impactRating: opportunity.impact_rating,
        timeline: opportunity.timeline,
        investmentRange: opportunity.investment_range,
    }))
}

function deriveEbitdaUplift(tree: EbitdaTree | undefined): EbitdaUpliftBar | null {
    if (!tree) return null
    if (!tree.revenueEstimate && !tree.ebitdaEstimate && !tree.businessModelSummary) {
        return null
    }
    return {
        revenueEstimate: tree.revenueEstimate,
        ebitdaEstimate: tree.ebitdaEstimate,
        summary: tree.businessModelSummary,
    }
}

/**
 * Pull the first sentence out of a rationale string. Falls back to the
 * full string when no sentence-ending punctuation is found, so the
 * summary always has SOMETHING to render when a rationale was provided.
 *
 * Empty input → empty output (the component skips the line).
 */
function getFirstSentence(text: string | undefined): string {
    if (!text) return ''
    const trimmed = text.trim()
    if (!trimmed) return ''
    const match = trimmed.match(/^[^.!?]+[.!?]/)
    return match ? match[0].trim() : trimmed
}
