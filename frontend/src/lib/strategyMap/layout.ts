import type { Edge, Node } from '@xyflow/react'

import type {
    CapacityObjective,
    ConfidenceMarker,
    CustomerObjective,
    FinancialObjective,
    InternalProcessObjective,
    InternalProcessTheme,
    StrategyMap,
} from '@/lib/types/api'

/**
 * Layout helper for the strategy-map canvas.
 *
 * Pure functions — no React imports — so the algorithm is unit-testable
 * without rendering. The renderer (`StrategyMapView`) calls
 * `buildStrategyMapGraph(strategyMap)` once per render and feeds the
 * `{ nodes, edges }` straight into React Flow.
 *
 * Column-assignment is the "α′ layout" defined in the change's
 * `design.md` (decision D2):
 *
 *   1. Financial objective F* → column of the InternalProcessTheme
 *      that lists F* in `supports_financial_objectives`. First listed
 *      theme wins on tie.
 *   2. Internal Process objective I* → column of its enclosing theme
 *      (theme order = column index).
 *   3. Customer objective C* → column of the Financial chip(s) it
 *      targets via outbound arrows. Fall back to the column of the
 *      Internal Process chip(s) that target it via inbound arrows.
 *      Fall back to the centre "shared" lane.
 *   4. Capacity objective O.* → column of the Internal Process
 *      chip(s) it targets via outbound arrows. Fall back to a
 *      capacity-specific spread so People/Technology/Culture don't
 *      stack on each other when arrows are sparse.
 *
 * Arrows whose `from`/`to` reference an unknown chip ID are dropped
 * (with a `console.warn` in development builds) — known AI-output
 * failure mode, see arch-review feedback on PR #239.
 */

// ── Public types ──────────────────────────────────────────────────────────

/** Vertical band each chip belongs to. Determines the chip's `y`. */
export type Perspective = 'financial' | 'customer' | 'internal' | 'capacity'

/** Capacity perspective uses three fixed buckets (Vector house style). */
export type CapacityBucket = 'People' | 'Technology' | 'Culture'

/**
 * Data carried on every strategy-map React Flow node. The node component
 * (`StrategyMapNode`) reads these fields to render its chip + tooltip.
 *
 * Indexed by `Record<string, unknown>` so it satisfies React Flow's
 * `Node<TData>` constraint (which requires the data to be an indexable
 * record, same convention as `EbitdaNodeData`).
 */
export interface StrategyMapNodeData extends Record<string, unknown> {
    objectiveId: string
    perspective: Perspective
    /** Display title. Renderer wraps in quotes for `customerVoice` chips. */
    title: string
    definition: string
    confidence: ConfidenceMarker
    /** Optional traceability note. Null when AI didn't supply one. */
    rationaleSource: string | null
    /** Customer perspective: render title with quotation marks + italic. */
    customerVoice: boolean
    /** Capacity perspective only: which of the three triad buckets. */
    capacityBucket?: CapacityBucket
    /**
     * True when the chip's column couldn't be derived from schema or arrows
     * and it landed in the centre "shared" lane. The renderer uses this to
     * apply a visual marker (dashed left border) so the reader can spot
     * "no theme home" chips at a glance rather than having to infer it
     * from X position alone. Goes away under the planned `β` follow-up
     * (deterministic theme membership for every objective).
     */
    inSharedLane: boolean
}

/**
 * Edge data — carries the cause-effect hypothesis. Used by the
 * canvas's edge tooltip.
 */
export interface StrategyMapEdgeData extends Record<string, unknown> {
    hypothesis: string
}

export interface StrategyMapGraph {
    nodes: Node<StrategyMapNodeData>[]
    edges: Edge<StrategyMapEdgeData>[]
}

// ── Layout constants ──────────────────────────────────────────────────────

/** Vertical distance between perspective bands. */
export const BAND_HEIGHT = 160

/** Horizontal distance between theme columns. */
export const COLUMN_WIDTH = 280

/** Horizontal width of one chip slot within a column. */
export const SLOT_WIDTH = 240

/** Gap between chips that share a column (e.g. multiple I* in one theme). */
export const SLOT_GAP = 16

/** Vertical offset within a band (gives the chip room above/below the band line). */
const BAND_PADDING = 24

/**
 * The four perspective bands rendered top→bottom. Index = `y / BAND_HEIGHT`.
 * Order matches K&N canonical: financial outcomes at the top, capacity
 * (the underlying enabler) at the bottom.
 */
const PERSPECTIVE_ROW: Record<Perspective, number> = {
    financial: 0,
    customer: 1,
    internal: 2,
    capacity: 3,
}

// ── Public entry point ────────────────────────────────────────────────────

/**
 * Build the React Flow graph from a `StrategyMap`. Pure function.
 *
 * Caller is responsible for passing the result to React Flow's
 * `nodes`/`edges` props (or the `useNodesState` initial value). The
 * function does not mutate the input.
 */
export function buildStrategyMapGraph(strategyMap: StrategyMap): StrategyMapGraph {
    const themeNames = strategyMap.internalProcesses.themes.map((t) => t.name)
    const totalColumns = Math.max(themeNames.length, 1)

    // First pass — assign each chip a (column, slot) position.
    // Slot indices within a (band, column) are auto-incremented as
    // chips are appended; the final pixel offset is computed below.
    const placements = assignPlacements(strategyMap, totalColumns)

    // Second pass — compute pixel coordinates and build React Flow nodes.
    const nodes = placements.map((p) => buildNode(p, totalColumns))

    // Third pass — validate and build edges.
    const objectiveIdSet = new Set(placements.map((p) => p.data.objectiveId))
    const edges = buildEdges(strategyMap.arrows, objectiveIdSet)

    return { nodes, edges }
}

// ── Placement pass ────────────────────────────────────────────────────────

interface ChipPlacement {
    data: StrategyMapNodeData
    /** Column index. `null` ⇒ centre "shared" lane. */
    column: number | null
    /** Slot offset within the (band, column). 0 = first chip in that slot. */
    slot: number
}

function assignPlacements(strategyMap: StrategyMap, totalColumns: number): ChipPlacement[] {
    const themes = strategyMap.internalProcesses.themes
    const placements: ChipPlacement[] = []

    // Track next slot per (perspective, columnKey) so chips in the same
    // column on the same band lay out side-by-side.
    const slotCounters = new SlotCounter()

    // 1. Financial — column from `supports_financial_objectives`.
    const financialColumnByOid = mapFinancialColumns(themes)
    for (const obj of strategyMap.financial.objectives) {
        const column = financialColumnByOid.get(obj.id) ?? null
        placements.push({
            data: financialNodeData(obj),
            column,
            slot: slotCounters.next('financial', column),
        })
    }

    // 2. Internal Processes — column from theme nesting.
    themes.forEach((theme, themeIndex) => {
        for (const obj of theme.objectives) {
            placements.push({
                data: internalNodeData(obj),
                column: themeIndex,
                slot: slotCounters.next('internal', themeIndex),
            })
        }
    })

    // 3. Customer — follow arrows. Build a quick-lookup for arrow inference.
    const arrowsByFrom = groupArrowsByFrom(strategyMap.arrows)
    const arrowsByTo = groupArrowsByTo(strategyMap.arrows)
    const objectiveColumnLookup = buildColumnLookupFromPlacements(placements)
    for (const obj of strategyMap.customer.objectives) {
        const column = inferCustomerColumn(obj.id, arrowsByFrom, arrowsByTo, objectiveColumnLookup)
        placements.push({
            data: customerNodeData(obj),
            column,
            slot: slotCounters.next('customer', column),
        })
    }

    // 4. Capacity — follow arrows; fall back to a People/Tech/Culture spread
    // so the three chips don't all collapse into the centre lane.
    const capacityChips: Array<{ obj: CapacityObjective; bucket: CapacityBucket }> = [
        { obj: strategyMap.organizationalCapacity.people, bucket: 'People' },
        { obj: strategyMap.organizationalCapacity.technology, bucket: 'Technology' },
        { obj: strategyMap.organizationalCapacity.culture, bucket: 'Culture' },
    ]
    capacityChips.forEach(({ obj, bucket }, index) => {
        const inferred = inferCapacityColumn(obj.id, arrowsByFrom, objectiveColumnLookup)
        // Fall-back spread: put People/Tech/Culture into evenly-distributed
        // columns when arrow inference yields nothing, so the band reads as
        // a triad rather than a stack.
        const column = inferred ?? capacityFallbackColumn(index, totalColumns)
        placements.push({
            data: capacityNodeData(obj, bucket),
            column,
            slot: slotCounters.next('capacity', column),
        })
    })

    return placements
}

// ── Per-perspective node-data builders ────────────────────────────────────

// Note: every per-perspective builder defaults `inSharedLane: false` here.
// The actual value is computed in `buildNode` (where `column === null` ⇒
// the chip ended up in the centre lane). Doing it once at build time keeps
// these builders pure and simple.

function financialNodeData(obj: FinancialObjective): StrategyMapNodeData {
    return {
        objectiveId: obj.id,
        perspective: 'financial',
        title: obj.title,
        definition: obj.definition,
        confidence: obj.confidence,
        rationaleSource: obj.rationale_source ?? null,
        customerVoice: false,
        inSharedLane: false,
    }
}

function customerNodeData(obj: CustomerObjective): StrategyMapNodeData {
    return {
        objectiveId: obj.id,
        perspective: 'customer',
        title: obj.title,
        definition: obj.definition,
        confidence: obj.confidence,
        rationaleSource: obj.rationale_source ?? null,
        customerVoice: true,
        inSharedLane: false,
    }
}

function internalNodeData(obj: InternalProcessObjective): StrategyMapNodeData {
    return {
        objectiveId: obj.id,
        perspective: 'internal',
        title: obj.title,
        definition: obj.definition,
        confidence: obj.confidence,
        rationaleSource: obj.rationale_source ?? null,
        customerVoice: false,
        inSharedLane: false,
    }
}

function capacityNodeData(obj: CapacityObjective, bucket: CapacityBucket): StrategyMapNodeData {
    return {
        objectiveId: obj.id,
        perspective: 'capacity',
        title: obj.title,
        definition: obj.definition,
        confidence: obj.confidence,
        rationaleSource: obj.rationale_source ?? null,
        customerVoice: false,
        capacityBucket: bucket,
        inSharedLane: false,
    }
}

// ── Column-assignment helpers ─────────────────────────────────────────────

/** Map every Financial-objective ID → first theme that lists it. */
function mapFinancialColumns(themes: InternalProcessTheme[]): Map<string, number> {
    const lookup = new Map<string, number>()
    themes.forEach((theme, index) => {
        for (const fId of theme.supports_financial_objectives) {
            // First-listed-theme wins. Don't overwrite a prior assignment.
            if (!lookup.has(fId)) {
                lookup.set(fId, index)
            }
        }
    })
    return lookup
}

function inferCustomerColumn(
    customerId: string,
    arrowsByFrom: Map<string, string[]>,
    arrowsByTo: Map<string, string[]>,
    columnLookup: Map<string, number | null>
): number | null {
    // Outbound: customer → financial.
    //
    // Tie-break note: when a customer chip has arrows targeting Financial
    // chips in MULTIPLE different columns (e.g. C1 → F1 in column 0 AND
    // C1 → F2 in column 1), we deliberately take the first match
    // (`downstreamColumns[0]`). The order is whatever the AI emitted in
    // its `arrows[]` array, so the bias is "first arrow wins", not
    // "user intent wins". Acceptable for v1 because (1) multi-column-
    // target customer chips are rare in practice (most customer
    // objectives map to one financial outcome), (2) when it does
    // trigger the chip still lands on a real column rather than the
    // centre lane (still readable), and (3) the planned `β` follow-up
    // adds an explicit `theme` field on every objective, eliminating
    // arrow inference entirely. If multi-target customer chips become
    // common before β lands, upgrade this to majority-vote.
    const downstreamColumns = (arrowsByFrom.get(customerId) ?? [])
        .map((target) => columnLookup.get(target))
        .filter((col): col is number => typeof col === 'number')
    if (downstreamColumns.length > 0) {
        return downstreamColumns[0]
    }
    // Inbound: internal → customer. Same first-wins bias applies; same
    // mitigation rationale.
    const upstreamColumns = (arrowsByTo.get(customerId) ?? [])
        .map((source) => columnLookup.get(source))
        .filter((col): col is number => typeof col === 'number')
    if (upstreamColumns.length > 0) {
        return upstreamColumns[0]
    }
    return null
}

function inferCapacityColumn(
    capacityId: string,
    arrowsByFrom: Map<string, string[]>,
    columnLookup: Map<string, number | null>
): number | null {
    const targetColumns = (arrowsByFrom.get(capacityId) ?? [])
        .map((target) => columnLookup.get(target))
        .filter((col): col is number => typeof col === 'number')
    if (targetColumns.length > 0) {
        return targetColumns[0]
    }
    return null
}

/**
 * Even-spread fallback for capacity chips. Three chips → three positions.
 * The intent is "don't stack" rather than "be deterministic about which
 * chip goes where" — when arrows are absent we have no signal anyway.
 *
 * Returning `null` means "centre lane" (between columns); a number means
 * "snap to that column index".
 */
function capacityFallbackColumn(index: number, totalColumns: number): number | null {
    if (totalColumns <= 1) {
        // Only one column — spread by slot inside it (caller's slot offset
        // takes care of the visual separation).
        return 0
    }
    if (totalColumns === 2) {
        // People → column 0, Technology → centre lane, Culture → column 1.
        if (index === 0) return 0
        if (index === 2) return 1
        return null
    }
    // 3+ themes: place at column 0, the geometric middle, and the last column.
    if (index === 0) return 0
    if (index === 2) return totalColumns - 1
    return Math.floor(totalColumns / 2)
}

function buildColumnLookupFromPlacements(placements: ChipPlacement[]): Map<string, number | null> {
    const lookup = new Map<string, number | null>()
    for (const placement of placements) {
        lookup.set(placement.data.objectiveId, placement.column)
    }
    return lookup
}

// ── Slot counter ──────────────────────────────────────────────────────────

/** Tracks how many chips have been placed in each (perspective, column). */
class SlotCounter {
    private counts = new Map<string, number>()

    next(perspective: Perspective, column: number | null): number {
        const key = `${perspective}|${column ?? 'centre'}`
        const current = this.counts.get(key) ?? 0
        this.counts.set(key, current + 1)
        return current
    }
}

// ── Pixel-coordinate computation ──────────────────────────────────────────

function buildNode(placement: ChipPlacement, totalColumns: number): Node<StrategyMapNodeData> {
    const row = PERSPECTIVE_ROW[placement.data.perspective]
    const baseX = columnBaseX(placement.column, totalColumns)
    const slotOffset = placement.slot * (SLOT_WIDTH + SLOT_GAP)

    return {
        id: placement.data.objectiveId,
        type: 'strategyMap',
        // (x, y) is the top-left of the node.
        position: {
            x: baseX + slotOffset,
            y: row * BAND_HEIGHT + BAND_PADDING,
        },
        // Mark centre-lane chips so the renderer can apply a visual marker.
        // `column === null` is the canonical signal — see ChipPlacement.
        data: { ...placement.data, inSharedLane: placement.column === null },
        draggable: false,
        selectable: true,
    }
}

/** Pixel `x` of column 0's first slot. Centre lane sits between columns. */
function columnBaseX(column: number | null, totalColumns: number): number {
    if (column === null) {
        // Centre lane — midpoint of the canvas's column range.
        return ((totalColumns - 1) / 2) * COLUMN_WIDTH
    }
    return column * COLUMN_WIDTH
}

// ── Arrow building + validation ───────────────────────────────────────────

function groupArrowsByFrom(arrows: StrategyMap['arrows']): Map<string, string[]> {
    const map = new Map<string, string[]>()
    for (const arrow of arrows) {
        const list = map.get(arrow.from) ?? []
        list.push(arrow.to)
        map.set(arrow.from, list)
    }
    return map
}

function groupArrowsByTo(arrows: StrategyMap['arrows']): Map<string, string[]> {
    const map = new Map<string, string[]>()
    for (const arrow of arrows) {
        const list = map.get(arrow.to) ?? []
        list.push(arrow.from)
        map.set(arrow.to, list)
    }
    return map
}

function buildEdges(arrows: StrategyMap['arrows'], objectiveIds: Set<string>): Edge<StrategyMapEdgeData>[] {
    const edges: Edge<StrategyMapEdgeData>[] = []
    for (const arrow of arrows) {
        if (!objectiveIds.has(arrow.from) || !objectiveIds.has(arrow.to)) {
            // Known AI-output failure mode (see PR #239 review #2).
            // Drop the arrow; rest of the canvas renders normally.
            if (process.env.NODE_ENV !== 'production') {
                // eslint-disable-next-line no-console
                console.warn(
                    `[strategy-map] Dropping arrow with unknown endpoint(s): ${arrow.from} → ${arrow.to}`
                )
            }
            continue
        }
        edges.push({
            id: `${arrow.from}__${arrow.to}`,
            source: arrow.from,
            target: arrow.to,
            data: { hypothesis: arrow.hypothesis },
        })
    }
    return edges
}
