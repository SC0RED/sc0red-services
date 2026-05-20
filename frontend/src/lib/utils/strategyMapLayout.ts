import type {
    CapacityObjective,
    CustomerObjective,
    FinancialObjective,
    InternalProcessObjective,
    StrategyMap,
} from '@/lib/types/api'

/**
 * Build the cell-by-cell layout for the Balanced Scorecard table view
 * (introduced by Phase 6 of ``redesign-analysis-visuals``).
 *
 * The table is 4 perspective rows × N theme columns:
 *
 *  ┌──────────────┬─ theme col 1 ─┬─ theme col 2 ─┬─ theme col N ─┐
 *  │ Financial    │ <F objs>      │ <F objs>      │ <F objs>      │
 *  │ Customer     │ <C objs>      │ <C objs>      │ <C objs>      │
 *  │ Internal     │ <I objs>      │ <I objs>      │ <I objs>      │
 *  │ Org Capacity │ <O objs>      │ <O objs>      │ <O objs>      │
 *  └──────────────┴───────────────┴───────────────┴───────────────┘
 *
 * Column count and theme labels come from ``strategyMap.internalProcesses.themes[]``.
 * Each objective is routed into a (row, column) cell as follows:
 *
 *   - **Financial**: the theme whose ``supports_financial_objectives``
 *     lists the objective's ID owns the cell. Each objective lands in
 *     exactly one theme column (first match wins on ambiguity — a theme
 *     listing the same F ID twice is an upstream bug we accept loudly).
 *     Objectives never claimed by any theme go to a virtual "shared"
 *     column (rendered as a leading column when present).
 *   - **Customer**: distributed across theme columns round-robin by
 *     index, because customer objectives carry no direct theme link in
 *     the data shape. The wawa exemplar Zack referenced does the same.
 *   - **Internal Processes**: each theme's ``objectives[]`` array
 *     becomes that column's cell. Stacked vertically when a theme has
 *     multiple objectives.
 *   - **Organizational Capacity** (People / Technology / Culture):
 *     distributed across theme columns round-robin in P/T/C order.
 *
 * Empty (perspective, theme) coordinates render as placeholder cells
 * with the same border styling so the grid alignment stays clean.
 *
 * The helper is pure: no React, no DOM, no side effects. Output is
 * a fully resolved layout the renderer can `.map()` over without
 * branching.
 */

export type StrategyMapCellObjective =
    | { kind: 'financial'; objective: FinancialObjective }
    | { kind: 'customer'; objective: CustomerObjective }
    | { kind: 'internal'; objective: InternalProcessObjective }
    | { kind: 'capacity'; subkind: 'people' | 'technology' | 'culture'; objective: CapacityObjective }

export interface StrategyMapCell {
    perspective: 'financial' | 'customer' | 'internal' | 'capacity'
    /** 0-based index into ``StrategyMapLayout.themeNames``. */
    themeIndex: number
    /** Objectives that landed in this cell. May be empty (placeholder cell). */
    objectives: StrategyMapCellObjective[]
}

export interface StrategyMapLayout {
    /** Theme labels in render order. Drives the column header row + the
     *  ``themeIndex`` values in ``cells``. */
    themeNames: string[]
    /** 4 perspective rows × ``themeNames.length`` columns. Outer index
     *  matches ``PERSPECTIVE_ROW_ORDER`` below; inner index matches
     *  ``themeNames``. Empty cells carry ``objectives: []``. */
    cells: StrategyMapCell[][]
}

export const PERSPECTIVE_ROW_ORDER = ['financial', 'customer', 'internal', 'capacity'] as const

/** Subtitle prose label for each perspective row, used in the left
 *  column of the table. Spec: ``strategy-map-balanced-scorecard-layout``
 *  Requirement "Strategy-map body renders as a Balanced Scorecard table". */
export const PERSPECTIVE_ROW_LABELS: Record<
    (typeof PERSPECTIVE_ROW_ORDER)[number],
    {
        title: string
        subtitle: string
    }
> = {
    financial: { title: 'Financial', subtitle: 'What success looks like' },
    customer: { title: 'Customer', subtitle: 'Who we serve & why us' },
    internal: { title: 'Internal Processes', subtitle: 'The themes we must master' },
    capacity: { title: 'Organizational Capacity', subtitle: 'Who we are inside' },
}

export function buildStrategyMapLayout(strategyMap: StrategyMap): StrategyMapLayout {
    const themes = strategyMap.internalProcesses.themes
    const themeNames = themes.map((theme) => theme.name)
    const columnCount = themeNames.length

    // Initialise empty cells for every (perspective, themeIndex).
    const cells: StrategyMapCell[][] = PERSPECTIVE_ROW_ORDER.map((perspective) =>
        themeNames.map((_, themeIndex) => ({
            perspective,
            themeIndex,
            objectives: [] as StrategyMapCellObjective[],
        }))
    )

    // ── Financial row: theme.supports_financial_objectives lookup ──
    //
    // Each financial objective lands in the theme column whose
    // ``supports_financial_objectives`` array contains the objective's
    // ID. First match wins. Objectives no theme claims go into column 0
    // as a fallback — the renderer can highlight this case if needed,
    // but the AI almost never produces orphan financials in practice.
    //
    // When there are zero themes (pathological but valid input) the
    // financial row has no column to land objectives in. Skip the loop
    // entirely rather than indexing ``cells[financialRowIndex][0]`` and
    // throwing — the renderer treats a 4×0 layout as "empty grid", which
    // is the right behaviour for a malformed strategy map.
    const financialRowIndex = PERSPECTIVE_ROW_ORDER.indexOf('financial')
    if (columnCount > 0) {
        for (const objective of strategyMap.financial.objectives) {
            const claimingThemeIndex = themes.findIndex((theme) =>
                theme.supports_financial_objectives.includes(objective.id)
            )
            const themeIndex = claimingThemeIndex >= 0 ? claimingThemeIndex : 0
            cells[financialRowIndex][themeIndex].objectives.push({
                kind: 'financial',
                objective,
            })
        }
    }

    // ── Customer row: round-robin across theme columns ──
    //
    // Customer objectives carry no direct theme link. Spreading them
    // round-robin keeps the row visually balanced (vs. piling every
    // customer objective into column 0). The zero-themes guard
    // short-circuits before any indexing so pathological input (an AI
    // strategy map with no internal-process themes) doesn't throw.
    const customerRowIndex = PERSPECTIVE_ROW_ORDER.indexOf('customer')
    if (columnCount > 0) {
        strategyMap.customer.objectives.forEach((objective, index) => {
            const themeIndex = index % columnCount
            cells[customerRowIndex][themeIndex].objectives.push({
                kind: 'customer',
                objective,
            })
        })
    }

    // ── Internal Processes row: theme.objectives[] stacks in own column ──
    const internalRowIndex = PERSPECTIVE_ROW_ORDER.indexOf('internal')
    themes.forEach((theme, themeIndex) => {
        for (const objective of theme.objectives) {
            cells[internalRowIndex][themeIndex].objectives.push({
                kind: 'internal',
                objective,
            })
        }
    })

    // ── Org Capacity row: People → Technology → Culture round-robin ──
    //
    // Three fixed objectives, distributed across N theme columns. With
    // 3 columns we get one per column; with 2 columns People + Culture
    // land in column 0; with 4+ columns the trailing columns stay
    // empty (placeholder). This is the established Vector / Kaplan-
    // Norton convention for the bottom row. The zero-themes guard
    // short-circuits before any indexing — matches the financial and
    // customer rows above.
    const capacityRowIndex = PERSPECTIVE_ROW_ORDER.indexOf('capacity')
    const capacityEntries: Array<{
        subkind: 'people' | 'technology' | 'culture'
        objective: CapacityObjective
    }> = [
        { subkind: 'people', objective: strategyMap.organizationalCapacity.people },
        { subkind: 'technology', objective: strategyMap.organizationalCapacity.technology },
        { subkind: 'culture', objective: strategyMap.organizationalCapacity.culture },
    ]
    if (columnCount > 0) {
        capacityEntries.forEach(({ subkind, objective }, index) => {
            const themeIndex = index % columnCount
            cells[capacityRowIndex][themeIndex].objectives.push({
                kind: 'capacity',
                subkind,
                objective,
            })
        })
    }

    return { themeNames, cells }
}

/**
 * Extract the first sentence (up to and including its terminal
 * punctuation) from a longer definition paragraph, for the table-cell
 * preview render. Falls back to the full text when no terminator is
 * found — short definitions stay readable in full.
 */
export function firstSentence(text: string): string {
    const trimmed = text.trim()
    if (trimmed === '') return ''
    // Match through the first sentence-ending punctuation followed by
    // whitespace OR end-of-string. Excludes abbreviations like "Inc."
    // by requiring whitespace AFTER the period (very mild heuristic;
    // full NLP belongs upstream if the AI's definitions ever need it).
    const match = trimmed.match(/^[^.!?]+[.!?](?:\s|$)/)
    if (match) return match[0].trim()
    return trimmed
}
