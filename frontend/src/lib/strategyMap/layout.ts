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

/**
 * Per-band layout metadata. One entry per perspective in
 * top-to-bottom order. ``top`` is the band's y in world coordinates;
 * ``height`` is the band's rendered height (dynamic — grows to fit
 * the tallest column in that band). Consumers (the canvas component,
 * the band-label renderer) use this so band labels and the canvas
 * height stay in sync with the chip layout.
 */
export interface StrategyMapBand {
    perspective: Perspective
    top: number
    height: number
}

export interface StrategyMapGraph {
    nodes: Node<StrategyMapNodeData>[]
    edges: Edge<StrategyMapEdgeData>[]
    /**
     * Per-band geometry — exposed so the canvas can size itself and
     * position band labels without re-deriving the math. Length = 4
     * (one per perspective in top-to-bottom narrative order).
     */
    bands: StrategyMapBand[]
}

// ── Layout constants ──────────────────────────────────────────────────────
//
// Slots stack VERTICALLY within a column (canonical K&N pattern: when a
// theme has multiple objectives in one perspective, they're listed
// downward inside the band). Earlier versions stacked horizontally with
// a per-slot x-offset, but with ``CHIP_WIDTH = 220`` and
// ``COLUMN_WIDTH = 280`` the slot-1 chip would extend past the column
// boundary and visually overlap the next column's chip (the production
// bug from PR #239). Vertical stacking keeps each column's chips inside
// their column at the cost of a band that grows to fit its tallest
// column.

/** Pixel width of a chip. Drives column geometry and text truncation. */
export const CHIP_WIDTH = 220

/** Pixel height of a chip. Drives band-height computation. */
export const CHIP_HEIGHT = 64

/** Horizontal distance between theme columns. */
export const COLUMN_WIDTH = 280

/**
 * Vertical offset between successive slots in the same (band, column).
 * One slot's worth of space = the chip's height plus a small gap; the
 * gap is intentionally narrow so multi-slot columns stay visually
 * grouped within their band.
 */
export const SLOT_Y_OFFSET = 76

/**
 * Minimum band height. Bands with a single short slot would otherwise
 * look cramped against the band-divider rules; this floor preserves
 * visual rhythm across bands of varying objective counts.
 */
export const MIN_BAND_HEIGHT = 180

/**
 * Vertical padding inside a band (above the first chip and below the
 * last). Used both for chip y-positioning within a band and for the
 * band-height calculation.
 */
const BAND_PADDING = 24

/**
 * The four perspective bands rendered top→bottom. Order matters for
 * the rendered narrative and for the cumulative-top calculation when
 * bands grow to fit their chips.
 */
const PERSPECTIVE_ORDER: ReadonlyArray<Perspective> = ['financial', 'customer', 'internal', 'capacity']

/**
 * Compatibility export — kept so existing tests + callers that reference
 * the historical fixed band height continue to compile. New code SHOULD
 * use ``StrategyMapGraph.bands[i].height`` (per-band dynamic height) or
 * ``MIN_BAND_HEIGHT`` (the floor used by the dynamic calculation)
 * instead.
 *
 * @deprecated Use ``MIN_BAND_HEIGHT`` for the floor, or read the actual
 * band height from ``StrategyMapGraph.bands``.
 */
export const BAND_HEIGHT = MIN_BAND_HEIGHT

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

    // Second pass — compute dynamic band geometry from the placements.
    // Each band's height grows to fit the column with the most slots
    // in that band. The cumulative band top is the sum of all prior
    // band heights. Bands are returned in top-to-bottom order.
    const bands = computeBandGeometry(placements)
    const bandLookup = new Map<Perspective, StrategyMapBand>(bands.map((band) => [band.perspective, band]))

    // Third pass — compute pixel coordinates and build React Flow nodes.
    const nodes = placements.map((p) => buildNode(p, totalColumns, bandLookup))

    // Fourth pass — validate and build edges.
    const objectiveIdSet = new Set(placements.map((p) => p.data.objectiveId))
    const edges = buildEdges(strategyMap.arrows, objectiveIdSet)

    return { nodes, edges, bands }
}

// ── Band-geometry pass ────────────────────────────────────────────────────

/**
 * Total canvas height = sum of all per-band heights. Convenience for
 * the canvas component which needs to size its container.
 */
export function totalCanvasHeight(bands: StrategyMapBand[]): number {
    if (bands.length === 0) return MIN_BAND_HEIGHT * PERSPECTIVE_ORDER.length
    const lastBand = bands[bands.length - 1]
    return lastBand.top + lastBand.height
}

/**
 * Compute per-band geometry from the placements list.
 *
 * For each perspective we find the maximum slot count across all its
 * (column-keyed) groups — that's how tall the tallest column in that
 * band is. The band's height grows to fit it (clamped to a minimum
 * floor for visual rhythm). Heights stack to produce the band tops.
 */
function computeBandGeometry(placements: ChipPlacement[]): StrategyMapBand[] {
    // For each perspective, track the maximum slot count seen across
    // any (column) within that band. Slot index is zero-based, so the
    // count is ``maxSlot + 1``.
    const maxSlotByPerspective: Record<Perspective, number> = {
        financial: 0,
        customer: 0,
        internal: 0,
        capacity: 0,
    }
    for (const placement of placements) {
        const current = maxSlotByPerspective[placement.data.perspective]
        if (placement.slot + 1 > current) {
            maxSlotByPerspective[placement.data.perspective] = placement.slot + 1
        }
    }

    let cumulativeTop = 0
    const bands: StrategyMapBand[] = []
    for (const perspective of PERSPECTIVE_ORDER) {
        const slotCount = Math.max(1, maxSlotByPerspective[perspective])
        // Height = top padding + (slot 0 chip) + ((slotCount - 1) gaps) + bottom padding.
        // Each subsequent slot adds SLOT_Y_OFFSET; the chip itself is
        // CHIP_HEIGHT tall; padding sits above the first chip and below
        // the last. Clamp to MIN_BAND_HEIGHT for visual rhythm.
        const requiredHeight = BAND_PADDING + (slotCount - 1) * SLOT_Y_OFFSET + CHIP_HEIGHT + BAND_PADDING
        const height = Math.max(MIN_BAND_HEIGHT, requiredHeight)
        bands.push({ perspective, top: cumulativeTop, height })
        cumulativeTop += height
    }
    return bands
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

function buildNode(
    placement: ChipPlacement,
    totalColumns: number,
    bandLookup: Map<Perspective, StrategyMapBand>
): Node<StrategyMapNodeData> {
    const band = bandLookup.get(placement.data.perspective)
    if (band === undefined) {
        // Programming error — every perspective is in PERSPECTIVE_ORDER
        // and therefore in the bandLookup. Fail loudly rather than place
        // a chip at an unknown y.
        throw new Error(
            `Strategy-map layout: no band geometry found for perspective ${placement.data.perspective}`
        )
    }
    const baseX = columnBaseX(placement.column, totalColumns)
    // Slots stack vertically inside their (band, column). The y is the
    // band's dynamic top plus the in-band padding plus this slot's
    // offset within the band.
    const slotYOffset = placement.slot * SLOT_Y_OFFSET

    return {
        id: placement.data.objectiveId,
        type: 'strategyMap',
        // (x, y) is the top-left of the node.
        position: {
            x: baseX,
            y: band.top + BAND_PADDING + slotYOffset,
        },
        // Mark centre-lane chips so the renderer can apply a visual marker.
        // `column === null` is the canonical signal — see ChipPlacement.
        data: { ...placement.data, inSharedLane: placement.column === null },
        draggable: false,
        selectable: true,
    }
}

/**
 * Pixel `x` of a column's chips.
 *
 * Real columns: `column * COLUMN_WIDTH`.
 *
 * Shared-lane chips (`column === null`) are placed PAST the last real
 * column at `totalColumns * COLUMN_WIDTH`. Earlier versions tried to
 * position them BETWEEN two columns at the geometric centre; that
 * worked geometrically but the chip itself (`CHIP_WIDTH = 220`) is
 * wider than the gap between adjacent column chips
 * (`COLUMN_WIDTH - CHIP_WIDTH = 60`), so the shared-lane chip always
 * overlapped at least one neighbouring column chip in production. The
 * "rightmost virtual column" placement avoids overlap entirely; the
 * dashed left-border on the chip (set elsewhere in the renderer) still
 * communicates "doesn't belong to a theme".
 *
 * The renaming from "centre lane" to "shared lane" already happened in
 * the public type (`inSharedLane`). This function is the layout side
 * of that semantic.
 */
function columnBaseX(column: number | null, totalColumns: number): number {
    if (column === null) {
        // Shared lane sits past the last real column. Slot-y stacking
        // handles multiple shared-lane chips in the same band.
        return totalColumns * COLUMN_WIDTH
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
