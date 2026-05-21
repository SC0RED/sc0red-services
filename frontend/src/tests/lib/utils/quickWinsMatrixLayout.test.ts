import { describe, it, expect } from 'vitest'

import type { Opportunity } from '@/lib/types/api'
import {
    CLUSTER_THRESHOLD,
    INVESTMENT_MAX_USD,
    INVESTMENT_MIN_USD,
    ROI_MAX_PCT,
    buildQuickWinsMatrixLayout,
    projectInvestmentX,
    projectRoiY,
    quadrantFor,
} from '@/lib/utils/quickWinsMatrixLayout'

/**
 * Unit tests for the Phase-14 ROI × Investment scatter layout helper.
 * The helper has no React or DOM dependency, so these tests run on
 * raw arrays of opportunities + plot dimensions.
 */

const PLOT_W = 600
const PLOT_H = 400

const make = (overrides: Partial<Opportunity>): Opportunity => ({
    title: 'Test opp',
    description: 'desc',
    impact_rating: 'High',
    timeline: 'Quick Win (1-3 months)',
    strategic_category: 'Operational Efficiency',
    value_lever: 'Revenue Side',
    ...overrides,
})

// ── Axis projection ────────────────────────────────────────────────

describe('projectInvestmentX (log-scale X)', () => {
    it('maps INVESTMENT_MIN_USD to x = 0', () => {
        expect(projectInvestmentX(INVESTMENT_MIN_USD, PLOT_W)).toBeCloseTo(0)
    })

    it('maps INVESTMENT_MAX_USD to x = plotWidth', () => {
        expect(projectInvestmentX(INVESTMENT_MAX_USD, PLOT_W)).toBeCloseTo(PLOT_W)
    })

    it('places mid-decade investments along the log curve, not the linear midpoint', () => {
        // INVESTMENT_MIN_USD = 1e4, INVESTMENT_MAX_USD = 1e7 → 3 decades.
        // $100K is one decade into the range → 1/3 of the plot width,
        // not 1/100 (which a linear projection would yield).
        const x = projectInvestmentX(100_000, PLOT_W)
        expect(x).toBeCloseTo(PLOT_W / 3, 0)
    })

    it('clamps below-minimum investments to x = 0', () => {
        expect(projectInvestmentX(1_000, PLOT_W)).toBeCloseTo(0)
    })

    it('clamps above-maximum investments to x = plotWidth', () => {
        expect(projectInvestmentX(50_000_000, PLOT_W)).toBeCloseTo(PLOT_W)
    })
})

describe('projectRoiY (linear Y, SVG-inverted)', () => {
    it('maps 0% ROI to the BOTTOM of the plot (y = plotHeight)', () => {
        // SVG Y grows down, so 0% ROI = bottom of the chart.
        const { y, clampedUp } = projectRoiY(0, PLOT_H)
        expect(y).toBeCloseTo(PLOT_H)
        expect(clampedUp).toBe(false)
    })

    it('maps ROI_MAX_PCT to the TOP (y = 0)', () => {
        const { y, clampedUp } = projectRoiY(ROI_MAX_PCT, PLOT_H)
        expect(y).toBeCloseTo(0)
        expect(clampedUp).toBe(false)
    })

    it('flags clampedUp when ROI exceeds the cap', () => {
        // 450% → clamps visually at the top, caret renders.
        const { y, clampedUp } = projectRoiY(450, PLOT_H)
        expect(y).toBeCloseTo(0)
        expect(clampedUp).toBe(true)
    })

    it('places mid-range ROI proportionally', () => {
        // 150% = halfway between 0 and 300, so y = halfway down.
        const { y } = projectRoiY(150, PLOT_H)
        expect(y).toBeCloseTo(PLOT_H / 2)
    })
})

// ── Quadrant assignment ────────────────────────────────────────────

describe('quadrantFor', () => {
    // Plot origin at top-left, splits at (300, 200) for the test grid.
    it('assigns top-left to "quick-wins"', () => {
        expect(quadrantFor(100, 50, 300, 200)).toBe('quick-wins')
    })

    it('assigns top-right to "strategic-bets"', () => {
        expect(quadrantFor(500, 50, 300, 200)).toBe('strategic-bets')
    })

    it('assigns bottom-left to "fill-ins"', () => {
        expect(quadrantFor(100, 350, 300, 200)).toBe('fill-ins')
    })

    it('assigns bottom-right to "deprioritise"', () => {
        expect(quadrantFor(500, 350, 300, 200)).toBe('deprioritise')
    })

    it('treats dots on the split lines as belonging to the right/bottom halves', () => {
        // Dots exactly ON the median land in the right + bottom halves
        // via the ``< splitX`` / ``< splitY`` comparisons. Documented
        // here so a future refactor that flips the comparison can
        // catch the regression.
        expect(quadrantFor(300, 200, 300, 200)).toBe('deprioritise')
    })
})

// ── buildQuickWinsMatrixLayout ─────────────────────────────────────

describe('buildQuickWinsMatrixLayout — routing', () => {
    it('routes both-populated opportunities into the in-plot dots', () => {
        const layout = buildQuickWinsMatrixLayout(
            [make({ investment_value_usd: 100_000, roi_estimate_pct: 150 })],
            PLOT_W,
            PLOT_H
        )
        expect(layout.inPlot).toHaveLength(1)
        expect(layout.uncalibrated).toHaveLength(0)
        expect(layout.inPlot[0].opportunityIndex).toBe(0)
    })

    it('routes opportunities missing either axis into the uncalibrated strip', () => {
        const layout = buildQuickWinsMatrixLayout(
            [
                make({ investment_value_usd: 100_000, roi_estimate_pct: null }),
                make({ investment_value_usd: null, roi_estimate_pct: 50 }),
                make({ investment_value_usd: null, roi_estimate_pct: null }),
            ],
            PLOT_W,
            PLOT_H
        )
        expect(layout.inPlot).toHaveLength(0)
        expect(layout.uncalibrated).toHaveLength(3)
        expect(layout.uncalibrated.map((u) => u.opportunityIndex)).toEqual([0, 1, 2])
    })

    it('treats undefined the same as null (legacy persisted shape)', () => {
        const legacy = make({})
        // Don't set investment_value_usd or roi_estimate_pct at all.
        const layout = buildQuickWinsMatrixLayout([legacy], PLOT_W, PLOT_H)
        expect(layout.uncalibrated).toHaveLength(1)
    })
})

describe('buildQuickWinsMatrixLayout — quadrant medians', () => {
    it('splits at the median of the in-plot subset (not fixed thresholds)', () => {
        // Three opportunities all "low-investment" by any external
        // scale, but the median splits them relative to EACH OTHER —
        // the matrix shows the spread within this scan.
        const layout = buildQuickWinsMatrixLayout(
            [
                make({ investment_value_usd: 20_000, roi_estimate_pct: 250 }),
                make({ investment_value_usd: 40_000, roi_estimate_pct: 150 }),
                make({ investment_value_usd: 60_000, roi_estimate_pct: 50 }),
            ],
            PLOT_W,
            PLOT_H
        )
        // Median investment = $40K → splitX ≈ projectInvestmentX(40K).
        // The dot at $40K lands ON the median line; per quadrantFor it
        // goes to the right half. Verify the routing.
        const dotAtMedian = layout.inPlot.find((d) => d.opportunityIndex === 1)
        expect(dotAtMedian).toBeDefined()
        // At the median split point, our quadrantFor rule routes to
        // the right + bottom halves. With ROI = 150 (the median of the
        // three values), this dot lands in deprioritise (bottom-right).
        expect(dotAtMedian!.quadrant).toBe('deprioritise')
    })

    it('falls back to plot centre when there are no in-plot dots', () => {
        // All uncalibrated → quadrant labels still need a stable
        // anchor so the renderer can show the empty grid framework.
        const layout = buildQuickWinsMatrixLayout(
            [make({ investment_value_usd: null, roi_estimate_pct: null })],
            PLOT_W,
            PLOT_H
        )
        expect(layout.investmentSplitX).toBeCloseTo(PLOT_W / 2)
        expect(layout.roiSplitY).toBeCloseTo(PLOT_H / 2)
    })
})

describe('buildQuickWinsMatrixLayout — clamp + jitter + cluster', () => {
    it('flags clampedUp on dots whose ROI exceeds the cap', () => {
        const layout = buildQuickWinsMatrixLayout(
            [
                make({ investment_value_usd: 100_000, roi_estimate_pct: 50 }),
                make({ investment_value_usd: 200_000, roi_estimate_pct: 450 }),
            ],
            PLOT_W,
            PLOT_H
        )
        const lowRoi = layout.inPlot.find((d) => d.opportunityIndex === 0)!
        const highRoi = layout.inPlot.find((d) => d.opportunityIndex === 1)!
        expect(lowRoi.clampedUp).toBe(false)
        expect(highRoi.clampedUp).toBe(true)
    })

    it('jitters identical-coordinate opportunities so each stays individually addressable', () => {
        const layout = buildQuickWinsMatrixLayout(
            [
                make({ investment_value_usd: 100_000, roi_estimate_pct: 150 }),
                make({ investment_value_usd: 100_000, roi_estimate_pct: 150 }),
            ],
            PLOT_W,
            PLOT_H
        )
        expect(layout.inPlot).toHaveLength(2)
        const distance = Math.hypot(
            layout.inPlot[0].x - layout.inPlot[1].x,
            layout.inPlot[0].y - layout.inPlot[1].y
        )
        // Either separated by at least the dot diameter or by the
        // jitter radius — both leave each dot individually clickable.
        expect(distance).toBeGreaterThan(0)
    })

    it('collapses a single quadrant into a cluster pin when it exceeds CLUSTER_THRESHOLD', () => {
        // CLUSTER_THRESHOLD + 1 opportunities all in the High-ROI /
        // low-investment corner. The whole quadrant collapses.
        const count = CLUSTER_THRESHOLD + 1
        const opps = Array.from({ length: count }, () =>
            make({ investment_value_usd: 20_000, roi_estimate_pct: 250 })
        )
        const layout = buildQuickWinsMatrixLayout(opps, PLOT_W, PLOT_H)
        // No individual dots in that quadrant.
        expect(layout.quadrantDots['quick-wins']).toHaveLength(0)
        // Single cluster pin instead.
        expect(layout.clusterPins).toHaveLength(1)
        expect(layout.clusterPins[0].opportunityIndices).toHaveLength(count)
    })

    it('keeps dots individual when a quadrant has exactly CLUSTER_THRESHOLD entries', () => {
        // Boundary case — `> threshold` means equal is fine.
        const opps = Array.from({ length: CLUSTER_THRESHOLD }, () =>
            make({ investment_value_usd: 20_000, roi_estimate_pct: 250 })
        )
        const layout = buildQuickWinsMatrixLayout(opps, PLOT_W, PLOT_H)
        expect(layout.clusterPins).toHaveLength(0)
        expect(layout.inPlot.length + layout.uncalibrated.length).toBe(CLUSTER_THRESHOLD)
    })
})

describe('buildQuickWinsMatrixLayout — deterministic output', () => {
    it('produces identical (x, y) coordinates across re-renders for the same input', () => {
        const opps = [
            make({ investment_value_usd: 100_000, roi_estimate_pct: 150 }),
            make({ investment_value_usd: 200_000, roi_estimate_pct: 100 }),
            make({ investment_value_usd: 50_000, roi_estimate_pct: 200 }),
        ]
        const a = buildQuickWinsMatrixLayout(opps, PLOT_W, PLOT_H)
        const b = buildQuickWinsMatrixLayout(opps, PLOT_W, PLOT_H)
        expect(a.inPlot.map((d) => [d.x, d.y])).toEqual(b.inPlot.map((d) => [d.x, d.y]))
    })
})
