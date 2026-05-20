import type { Opportunity } from '@/lib/types/api'

/**
 * Pure layout helper for the Quick Wins 2×2 matrix introduced by
 * Phase 7 of ``redesign-analysis-visuals``. Pure means: no React, no
 * DOM, no side effects (except a development-mode ``console.warn``
 * for unrecognised ``timeline`` strings — see scenario "Unrecognised
 * timeline string falls back to Medium-term" in the
 * ``quick-wins-matrix`` spec).
 *
 * The matrix is a 3×3 grid that visually collapses into four
 * conceptual quadrants:
 *
 *                Quick Win   Medium-term   Long-term
 *                ┌─────────┬─────────────┬──────────┐
 *  High impact   │ Quick   │             │ Strategic│
 *                │  Wins   │             │  Bets    │
 *                ├─────────┼─────────────┼──────────┤
 *  Medium impact │         │             │          │
 *                ├─────────┼─────────────┼──────────┤
 *  Low impact    │ Fill-   │             │  Avoid   │
 *                │  Ins    │             │ (label:  │
 *                │         │             │  Depri-  │
 *                │         │             │  oritise)│
 *                └─────────┴─────────────┴──────────┘
 *
 * Y-axis bucketing on ``Opportunity.impact_rating`` (a Pydantic-bound
 * enum, no fallback needed). X-axis bucketing on ``timeline`` (free-
 * text from the AI) by prefix match: "Quick" → 0, "Medium" → 1,
 * "Long" → 2. Anything else is logged in dev and falls into the
 * Medium-term column (matches the spec).
 */

export type ImpactRow = 'High' | 'Medium' | 'Low'
export type TimelineColumn = 'quick' | 'medium' | 'long'

/** Quadrant identity for each (row, col). Used by the renderer to
 *  drop muted labels into the four corner cells. */
export type Quadrant = 'quick-wins' | 'strategic-bets' | 'fill-ins' | 'deprioritise' | null

export interface QuickWinsMatrixCell {
    impact: ImpactRow
    timeline: TimelineColumn
    quadrant: Quadrant
    /** Original positions in ``opportunities`` for every opportunity
     *  that landed in this cell. Sorted by ``strategic_category`` then
     *  by index for stable ordering across renders. */
    opportunityIndices: number[]
}

export interface QuickWinsMatrixLayout {
    /** 3 rows (High / Medium / Low) × 3 cols (quick / medium / long). */
    cells: QuickWinsMatrixCell[][]
}

export const IMPACT_ROW_ORDER: readonly ImpactRow[] = ['High', 'Medium', 'Low']
export const TIMELINE_COLUMN_ORDER: readonly TimelineColumn[] = ['quick', 'medium', 'long']

export const TIMELINE_COLUMN_LABELS: Record<TimelineColumn, string> = {
    quick: 'Quick Win',
    medium: 'Medium-term',
    long: 'Long-term',
}

/** Quadrant labels rendered as muted overlays inside the four corner
 *  cells. The two center-axis cells (row 1 / col 1) carry no quadrant
 *  label — they're shared territory between the quadrants. */
export const QUADRANT_LABELS: Record<Exclude<Quadrant, null>, string> = {
    'quick-wins': 'Quick Wins',
    'strategic-bets': 'Strategic Bets',
    'fill-ins': 'Fill-Ins',
    deprioritise: 'Deprioritise',
}

/**
 * Bucket a free-text ``timeline`` string into one of three columns.
 * Spec rule: prefix match on "Quick" / "Medium" / "Long" (case-
 * insensitive). Anything else falls into Medium-term with a console
 * warning in development.
 *
 * Exported separately so tests can pin the rule without going through
 * the full matrix-build path.
 */
export function bucketTimeline(timeline: string): TimelineColumn {
    const trimmed = timeline.trim().toLowerCase()
    if (trimmed.startsWith('quick')) return 'quick'
    if (trimmed.startsWith('medium')) return 'medium'
    if (trimmed.startsWith('long')) return 'long'
    // Dev-mode loud-fail: surfaces drift in AI output formats without
    // breaking production rendering. ``process.env.NODE_ENV`` is the
    // canonical guard the rest of the codebase uses for dev-only
    // diagnostics.
    if (process.env.NODE_ENV !== 'production') {
        // eslint-disable-next-line no-console
        console.warn(
            `[QuickWinsMatrix] Unrecognised timeline string "${timeline}" — defaulting to Medium-term column.`
        )
    }
    return 'medium'
}

/** Quadrant identity for a (row, col) coordinate. Center-axis cells
 *  (the Medium impact row + the Medium-term column) carry no
 *  quadrant — quadrants are corner-only territory. */
export function quadrantFor(impact: ImpactRow, timeline: TimelineColumn): Quadrant {
    if (impact === 'High' && timeline === 'quick') return 'quick-wins'
    if (impact === 'High' && timeline === 'long') return 'strategic-bets'
    if (impact === 'Low' && timeline === 'quick') return 'fill-ins'
    if (impact === 'Low' && timeline === 'long') return 'deprioritise'
    return null
}

/**
 * Build the 3×3 layout from the opportunities array. Each opportunity
 * lands in exactly one cell; ``opportunityIndices`` arrays are
 * sorted-by-strategic-category-then-index so the dot render order is
 * stable across re-renders (matches the spec's "sorted by
 * strategic_category then by opportunity index" rule).
 */
export function buildQuickWinsMatrixLayout(opportunities: Opportunity[]): QuickWinsMatrixLayout {
    const cells: QuickWinsMatrixCell[][] = IMPACT_ROW_ORDER.map((impact) =>
        TIMELINE_COLUMN_ORDER.map((timeline) => ({
            impact,
            timeline,
            quadrant: quadrantFor(impact, timeline),
            opportunityIndices: [] as number[],
        }))
    )

    opportunities.forEach((opportunity, index) => {
        const rowIndex = IMPACT_ROW_ORDER.indexOf(opportunity.impact_rating)
        const colKey = bucketTimeline(opportunity.timeline)
        const colIndex = TIMELINE_COLUMN_ORDER.indexOf(colKey)
        // ``impact_rating`` is typed as ``'High' | 'Medium' | 'Low'`` so
        // ``rowIndex`` is always >= 0 — no fallback needed. A malformed
        // payload that bypasses TS at the API boundary would surface as
        // an out-of-range push, which is the right loud failure: a bug
        // in the upstream contract, not a user error to suppress.
        cells[rowIndex][colIndex].opportunityIndices.push(index)
    })

    // Stable sort: by strategic_category alphabetically, then by index
    // (insertion order) as a tiebreaker. The index tiebreaker keeps
    // equal-category dots in their original opportunities-array order.
    for (const row of cells) {
        for (const cell of row) {
            cell.opportunityIndices.sort((a, b) => {
                const catA = opportunities[a].strategic_category
                const catB = opportunities[b].strategic_category
                if (catA < catB) return -1
                if (catA > catB) return 1
                return a - b
            })
        }
    }

    return { cells }
}
