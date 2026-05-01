import type { Opportunity } from '@/lib/types/api'

/**
 * One opportunity paired with its position in the original API array.
 *
 * The `originalIndex` is the linchpin of the print PDF's cross-section
 * linkage: the EBITDA tree and the value-chain analysis carry
 * `linked_opportunity_indices` / `opportunity_indices` arrays that point
 * into the unsorted `opportunities` API array. We want to display
 * opportunities sorted by impact in the rendered PDF, so each card
 * carries both:
 *
 *   - `printedIndex`: 1-based position the reader sees ("Opportunity #3")
 *   - `originalIndex`: 0-based API position used for linkage resolution
 *
 * Linkage callouts use `originalIndex` to find the opportunity, and
 * `printedIndex` to render the human-friendly reference.
 */
export interface OpportunityWithIndex {
    opportunity: Opportunity
    /** 0-based position in the original `opportunities` API array. */
    originalIndex: number
    /** 1-based position in the sorted PDF render order. */
    printedIndex: number
}

const IMPACT_RANK: Record<string, number> = {
    High: 0,
    Medium: 1,
    Low: 2,
}

/**
 * Sort opportunities by impact (High → Medium → Low) then by original
 * index, returning each one paired with its original-index for linkage.
 *
 * Stable sort: when two opportunities tie on impact, the one that was
 * earlier in the API array sorts earlier in the PDF, so the API's
 * implicit ordering is preserved within each impact band.
 *
 * Empty input returns an empty array. Unknown `impact_rating` values
 * (shouldn't happen — the type narrows to High/Medium/Low — but defend
 * against bad upstream data) sort after Low.
 */
export function sortOpportunities(opportunities: Opportunity[]): OpportunityWithIndex[] {
    return opportunities
        .map((opportunity, originalIndex) => ({ opportunity, originalIndex }))
        .sort((a, b) => {
            const impactA = IMPACT_RANK[a.opportunity.impact_rating] ?? 3
            const impactB = IMPACT_RANK[b.opportunity.impact_rating] ?? 3
            if (impactA !== impactB) return impactA - impactB
            return a.originalIndex - b.originalIndex
        })
        .map((entry, sortedPosition) => ({
            opportunity: entry.opportunity,
            originalIndex: entry.originalIndex,
            printedIndex: sortedPosition + 1,
        }))
}

/**
 * Look up an opportunity in the sorted array by its original API index.
 *
 * Used by EBITDA / value-chain linkage callouts: those sections store
 * indices into the API array, but the print PDF renders the cards in
 * impact-sorted order. This resolver walks the sorted list once to
 * find the matching entry. O(n) per call is fine — linkage arrays
 * are small (typically 1–3 entries) and the sorted list is bounded by
 * total opportunity count (≤30 in practice).
 */
export function findByOriginalIndex(
    sorted: OpportunityWithIndex[],
    originalIndex: number
): OpportunityWithIndex | undefined {
    return sorted.find((entry) => entry.originalIndex === originalIndex)
}
