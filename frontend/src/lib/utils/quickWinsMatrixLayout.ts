import type { Opportunity } from '@/lib/types/api'

/**
 * Pure layout helper for the ROI × Investment Quick Wins matrix.
 * Phase 14 of ``redesign-analysis-visuals`` (design D8) replaced the
 * 3×3 categorical matrix (impact × timeline) with a true 2D scatter
 * plot on numeric ``investment_value_usd`` (X) × ``roi_estimate_pct``
 * (Y) — what Diagnostic Tool Feedback #6 originally asked for.
 *
 * The helper has no React or DOM dependency. Given a list of
 * opportunities and the SVG plot dimensions, it returns:
 *
 *   - ``inPlot``: opportunities that have BOTH numeric axes, with
 *     computed (x, y) pixel positions inside the plot area, the
 *     quadrant they belong to, and a clamp flag when ROI > 300 %.
 *   - ``uncalibrated``: opportunities with EITHER axis missing
 *     (``null`` / undefined). The renderer routes these into a
 *     horizontal strip below the scatter rather than placing them
 *     at fake coordinates.
 *   - ``investmentMedian``, ``roiMedian``: pixel coordinates of the
 *     quadrant split lines. Medians are computed over the in-plot
 *     subset so the quadrant labels stay meaningful regardless of
 *     the scan's absolute scale.
 *   - ``clusterPin``: per-quadrant flag when > ``CLUSTER_THRESHOLD``
 *     opportunities land in one quadrant. The renderer collapses
 *     those into a single "+N more" pin. Quadrants below the
 *     threshold pass through to the individual-dot path.
 */

// ── Axis configuration ────────────────────────────────────────────

/** Log-scale X axis spans 10K → 10M USD. Tick labels at decade
 *  boundaries. Values below MIN clamp left; values above MAX clamp
 *  right. */
export const INVESTMENT_MIN_USD = 10_000
export const INVESTMENT_MAX_USD = 10_000_000

/** Linear Y axis spans 0 → 300 %. Values above MAX clamp top with a
 *  caret marker. The Pydantic model rejects values above 500 entirely;
 *  the visual clamp at 300 is independent of the data ceiling. */
export const ROI_MIN_PCT = 0
export const ROI_MAX_PCT = 300

/** Jitter offset (± px) applied when two dots would otherwise collide
 *  within ``DOT_DIAMETER`` of each other. Keeps every dot
 *  individually clickable. Internal — only consumed by ``applyJitter``
 *  in this module.
 *
 *  Sized against ``DOT_DIAMETER_PX`` so a single jitter step moves a
 *  colliding dot clear of its neighbour without further attempts. */
const JITTER_RADIUS_PX = 12

/** Render the dot at this diameter; pairs of opportunities closer
 *  than this in screen space trigger jitter. Internal.
 *
 *  The screen ``ScatterDot`` renders a 20 px badge with a 1.5 px
 *  stroke and a 30 px hover ring (radius 14 + 2 px stroke) wrapped
 *  around it. Sizing the threshold to the hover ring — not the badge
 *  — means a hovered dot's ring never overlaps a neighbour's ring,
 *  even in a jittered cluster. Print dots are smaller but reuse the
 *  same threshold so layout output stays identical across surfaces;
 *  paper density is lower than screen density, so a conservative
 *  threshold is fine. */
const DOT_DIAMETER_PX = 30

/** When a quadrant accumulates more than this many in-plot dots,
 *  collapse them into a "+N more" cluster pin. Spec D8. */
export const CLUSTER_THRESHOLD = 10

// ── Public types ──────────────────────────────────────────────────

export type Quadrant = 'quick-wins' | 'strategic-bets' | 'fill-ins' | 'deprioritise'

export const QUADRANT_LABELS: Record<Quadrant, string> = {
    'quick-wins': 'Quick Wins',
    'strategic-bets': 'Strategic Bets',
    'fill-ins': 'Fill-Ins',
    deprioritise: 'Deprioritise',
}

export interface InPlotDot {
    /** Index in the original ``opportunities`` array — same key the
     *  hover provider uses for cross-section pulse. */
    opportunityIndex: number
    /** Pixel position inside the plot area (origin at top-left of the
     *  drawable region; Y is inverted because SVG Y grows downward). */
    x: number
    y: number
    /** Quadrant the dot belongs to, computed relative to the per-scan
     *  medians (not fixed thresholds). */
    quadrant: Quadrant
    /** ``true`` when the original ROI was above ROI_MAX_PCT and the
     *  dot is rendered clamped at the top of the plot. Renderer adds
     *  a "↑" caret marker so the clamp is visible. */
    clampedUp: boolean
}

interface UncalibratedDot {
    opportunityIndex: number
}

export interface ClusterPin {
    quadrant: Quadrant
    /** All opportunity indices in this quadrant. The popover lists
     *  every entry when the user clicks the pin. */
    opportunityIndices: number[]
    /** Centroid pixel position of the cluster within the quadrant —
     *  the render target for the pin. */
    x: number
    y: number
}

interface QuickWinsMatrixLayout {
    /** Plot area dimensions echoed back so the renderer can size its
     *  SVG container consistently. */
    plotWidth: number
    plotHeight: number
    /** In-plot dots — every entry has populated x/y + quadrant. */
    inPlot: InPlotDot[]
    /** Opportunities routed to the uncalibrated footer strip
     *  (``investment_value_usd === null`` OR ``roi_estimate_pct === null``). */
    uncalibrated: UncalibratedDot[]
    /** X pixel position of the vertical quadrant-split line (median
     *  investment of the in-plot subset, in pixel space). */
    investmentSplitX: number
    /** Y pixel position of the horizontal quadrant-split line. */
    roiSplitY: number
    /** Quadrants that collapsed into a "+N more" cluster pin. Empty
     *  when no quadrant exceeded ``CLUSTER_THRESHOLD`` dots. The
     *  renderer omits individual dots for these quadrants and renders
     *  the pin in their place. */
    clusterPins: ClusterPin[]
    /** Quadrant assignment for every in-plot dot, split by quadrant
     *  for easy iteration in the renderer. */
    quadrantDots: Record<Quadrant, InPlotDot[]>
}

// ── Pure helpers ──────────────────────────────────────────────────

/**
 * Map a raw USD investment value to an X pixel position on the log
 * scale. Clamps to [INVESTMENT_MIN_USD, INVESTMENT_MAX_USD] before
 * the log transform so very-low and very-high outliers stick to the
 * axis ends rather than escaping the plot.
 */
export function projectInvestmentX(usd: number, plotWidth: number): number {
    const clamped = Math.max(INVESTMENT_MIN_USD, Math.min(INVESTMENT_MAX_USD, usd))
    const logMin = Math.log10(INVESTMENT_MIN_USD)
    const logMax = Math.log10(INVESTMENT_MAX_USD)
    const fraction = (Math.log10(clamped) - logMin) / (logMax - logMin)
    return fraction * plotWidth
}

/**
 * Map a raw ROI percentage to a Y pixel position. SVG Y grows down,
 * so 0 % sits at the bottom of the plot (``y = plotHeight``) and the
 * top of the plot is ``y = 0``. Values above ROI_MAX_PCT clamp at the
 * top (and the renderer adds a caret marker).
 */
export function projectRoiY(pct: number, plotHeight: number): { y: number; clampedUp: boolean } {
    const clampedUp = pct > ROI_MAX_PCT
    const clamped = Math.max(ROI_MIN_PCT, Math.min(ROI_MAX_PCT, pct))
    const fraction = (clamped - ROI_MIN_PCT) / (ROI_MAX_PCT - ROI_MIN_PCT)
    // Invert: high ROI = top of plot = small Y.
    const y = plotHeight - fraction * plotHeight
    return { y, clampedUp }
}

/**
 * Project a raw USD investment value to an X pixel for AXIS TICK
 * rendering. Same log mapping as ``projectInvestmentX`` but without
 * the input clamp — tick positions are seeded with the exact axis
 * endpoints (``INVESTMENT_MIN_USD`` and ``INVESTMENT_MAX_USD``), so
 * clamping would no-op anyway. Lives here so the screen + print
 * scatter components share one canonical helper.
 */
export function projectInvestmentTickX(tick: number, plotWidth: number): number {
    const logMin = Math.log10(INVESTMENT_MIN_USD)
    const logMax = Math.log10(INVESTMENT_MAX_USD)
    const fraction = (Math.log10(tick) - logMin) / (logMax - logMin)
    return fraction * plotWidth
}

/**
 * Project a raw ROI percentage to a Y pixel for AXIS TICK rendering.
 * Same linear mapping as ``projectRoiY`` but without the clamp flag —
 * tick positions are seeded with values inside [ROI_MIN_PCT,
 * ROI_MAX_PCT] so the flag is moot. Lives here so the screen + print
 * scatter components share one canonical helper.
 */
export function projectRoiTickY(tick: number, plotHeight: number): number {
    const fraction = (tick - ROI_MIN_PCT) / (ROI_MAX_PCT - ROI_MIN_PCT)
    return plotHeight - fraction * plotHeight
}

/**
 * Format a USD value for axis tick labels: ``$10K`` / ``$1M`` /
 * ``$5K``. Shared by screen + print so the two renders are guaranteed
 * to agree on tick label strings for the same axis configuration.
 */
export function formatInvestmentTick(usd: number): string {
    if (usd >= 1_000_000) return `$${usd / 1_000_000}M`
    if (usd >= 1_000) return `$${usd / 1_000}K`
    return `$${usd}`
}

/** Quadrant of a dot relative to a median split point. */
export function quadrantFor(dotX: number, dotY: number, splitX: number, splitY: number): Quadrant {
    const leftHalf = dotX < splitX
    const topHalf = dotY < splitY
    if (leftHalf && topHalf) return 'quick-wins'
    if (!leftHalf && topHalf) return 'strategic-bets'
    if (leftHalf && !topHalf) return 'fill-ins'
    return 'deprioritise'
}

/**
 * Median of a non-empty number array. Returns the middle element for
 * odd lengths, the average of the two middle elements for even
 * lengths. Empty array returns ``NaN`` — callers handle the empty
 * case explicitly (the renderer falls back to plot centre when there
 * are no in-plot dots).
 */
function median(values: number[]): number {
    if (values.length === 0) return Number.NaN
    const sorted = [...values].sort((a, b) => a - b)
    const mid = Math.floor(sorted.length / 2)
    return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid]
}

/**
 * Jitter overlapping dots by walking the list, comparing each new
 * position against everything already placed, and applying a small
 * offset (rotating around a circle) when a collision is detected.
 * Keeps every dot individually clickable without distorting the
 * scatter's overall shape.
 *
 * Deterministic — the jitter angle is keyed on the dot's position in
 * the input array so re-renders produce the same layout (which lets
 * tests pin specific offsets).
 */
function applyJitter(dots: InPlotDot[]): InPlotDot[] {
    const placed: InPlotDot[] = []
    for (let i = 0; i < dots.length; i += 1) {
        const candidate = { ...dots[i] }
        let attempt = 0
        const maxAttempts = 6
        while (attempt < maxAttempts) {
            const collides = placed.some(
                (p) => Math.hypot(p.x - candidate.x, p.y - candidate.y) < DOT_DIAMETER_PX
            )
            if (!collides) break
            // Rotate around a unit circle by ``attempt`` increments;
            // multiply by JITTER_RADIUS_PX. Keyed on the original
            // index ``i`` so identical-input arrays produce identical
            // layouts across renders.
            const angle = (Math.PI / 3) * (i + attempt)
            candidate.x = dots[i].x + Math.cos(angle) * JITTER_RADIUS_PX * (attempt + 1)
            candidate.y = dots[i].y + Math.sin(angle) * JITTER_RADIUS_PX * (attempt + 1)
            attempt += 1
        }
        placed.push(candidate)
    }
    return placed
}

// ── Layout build ──────────────────────────────────────────────────

/**
 * Build the full matrix layout from the raw opportunities array plus
 * the plot area dimensions (in pixels). Pure function — no DOM, no
 * React, no side effects.
 *
 * Routing rules:
 *
 *   - Both axes populated → in-plot dot at projected (x, y), assigned
 *     to a quadrant relative to the per-scan medians.
 *   - Either axis null/undefined → uncalibrated footer strip.
 *
 * Cluster collapse: when any quadrant has > ``CLUSTER_THRESHOLD``
 * in-plot dots after jittering, that quadrant's dots are replaced
 * with a single ``ClusterPin`` at the quadrant's centroid. The
 * individual dots are NOT carried in ``inPlot`` for collapsed
 * quadrants — only the pin survives.
 */
export function buildQuickWinsMatrixLayout(
    opportunities: Opportunity[],
    plotWidth: number,
    plotHeight: number
): QuickWinsMatrixLayout {
    const uncalibrated: UncalibratedDot[] = []
    const inPlotRaw: InPlotDot[] = []

    // First pass — bucket each opportunity into inPlot vs uncalibrated.
    opportunities.forEach((opportunity, index) => {
        const investment = opportunity.investment_value_usd
        const roi = opportunity.roi_estimate_pct
        if (investment == null || roi == null) {
            uncalibrated.push({ opportunityIndex: index })
            return
        }
        const x = projectInvestmentX(investment, plotWidth)
        const { y, clampedUp } = projectRoiY(roi, plotHeight)
        inPlotRaw.push({
            opportunityIndex: index,
            x,
            y,
            // Quadrant assignment is deferred until we know the
            // median split lines — placeholder value here.
            quadrant: 'quick-wins',
            clampedUp,
        })
    })

    // Second pass — compute medians from the in-plot subset, then
    // re-assign quadrants. Empty in-plot → split at the plot centre
    // (renderer shows the empty grid with quadrant labels intact).
    const investmentSplitX = inPlotRaw.length > 0 ? median(inPlotRaw.map((d) => d.x)) : plotWidth / 2
    const roiSplitY = inPlotRaw.length > 0 ? median(inPlotRaw.map((d) => d.y)) : plotHeight / 2

    const inPlotWithQuadrants = inPlotRaw.map((dot) => ({
        ...dot,
        quadrant: quadrantFor(dot.x, dot.y, investmentSplitX, roiSplitY),
    }))

    // Third pass — jitter overlapping dots so they stay individually
    // clickable. Run AFTER quadrant assignment so jitter doesn't bump
    // a dot across the median split line.
    const inPlotJittered = applyJitter(inPlotWithQuadrants)

    // Fourth pass — group by quadrant; collapse quadrants over
    // threshold into cluster pins.
    const byQuadrant: Record<Quadrant, InPlotDot[]> = {
        'quick-wins': [],
        'strategic-bets': [],
        'fill-ins': [],
        deprioritise: [],
    }
    for (const dot of inPlotJittered) {
        byQuadrant[dot.quadrant].push(dot)
    }

    const clusterPins: ClusterPin[] = []
    const finalInPlot: InPlotDot[] = []
    const finalByQuadrant: Record<Quadrant, InPlotDot[]> = {
        'quick-wins': [],
        'strategic-bets': [],
        'fill-ins': [],
        deprioritise: [],
    }

    ;(Object.keys(byQuadrant) as Quadrant[]).forEach((quadrant) => {
        const dots = byQuadrant[quadrant]
        if (dots.length > CLUSTER_THRESHOLD) {
            // Centroid of the quadrant — average position of all dots.
            const cx = dots.reduce((sum, d) => sum + d.x, 0) / dots.length
            const cy = dots.reduce((sum, d) => sum + d.y, 0) / dots.length
            clusterPins.push({
                quadrant,
                opportunityIndices: dots.map((d) => d.opportunityIndex),
                x: cx,
                y: cy,
            })
            // Suppress individual dots for this quadrant.
        } else {
            finalInPlot.push(...dots)
            finalByQuadrant[quadrant].push(...dots)
        }
    })

    return {
        plotWidth,
        plotHeight,
        inPlot: finalInPlot,
        uncalibrated,
        investmentSplitX,
        roiSplitY,
        clusterPins,
        quadrantDots: finalByQuadrant,
    }
}
