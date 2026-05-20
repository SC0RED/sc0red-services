import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import type { Opportunity } from '@/lib/types/api'
import { bucketTimeline, buildQuickWinsMatrixLayout, quadrantFor } from '@/lib/utils/quickWinsMatrixLayout'

/**
 * Unit tests for the pure Quick Wins matrix layout helper introduced
 * in P7 of ``redesign-analysis-visuals``. The helper has no React or
 * DOM dependency and runs on the raw ``Opportunity[]`` shape only.
 */

const make = (overrides: Partial<Opportunity>): Opportunity => ({
    title: 'Test opportunity',
    description: 'desc',
    impact_rating: 'High',
    timeline: 'Quick Win (1-3 months)',
    strategic_category: 'Operational Efficiency',
    value_lever: 'Revenue Side',
    ...overrides,
})

describe('bucketTimeline', () => {
    let warnSpy: ReturnType<typeof vi.spyOn>

    beforeEach(() => {
        warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    })

    afterEach(() => {
        warnSpy.mockRestore()
    })

    it('matches the "Quick" prefix into the quick column', () => {
        expect(bucketTimeline('Quick Win (1-3 months)')).toBe('quick')
        expect(bucketTimeline('quick fix')).toBe('quick')
    })

    it('matches the "Medium" prefix into the medium column', () => {
        expect(bucketTimeline('Medium-term (3-9 months)')).toBe('medium')
        expect(bucketTimeline('medium')).toBe('medium')
    })

    it('matches the "Long" prefix into the long column', () => {
        expect(bucketTimeline('Long-term (9+ months)')).toBe('long')
        expect(bucketTimeline('longer than expected')).toBe('long')
    })

    it('is whitespace-tolerant', () => {
        expect(bucketTimeline('  Quick Win  ')).toBe('quick')
    })

    it('falls back to medium with a dev-mode console.warn for unknown strings', () => {
        // The helper is meant to log loudly when AI output drifts.
        // Tests run in NODE_ENV=test which is !== 'production', so the
        // warn path executes.
        expect(bucketTimeline('Unspecified')).toBe('medium')
        expect(warnSpy).toHaveBeenCalledOnce()
        expect(warnSpy.mock.calls[0][0]).toContain('Unspecified')
        expect(warnSpy.mock.calls[0][0]).toContain('Medium-term')
    })
})

describe('quadrantFor', () => {
    it('assigns the four corners to their quadrants', () => {
        expect(quadrantFor('High', 'quick')).toBe('quick-wins')
        expect(quadrantFor('High', 'long')).toBe('strategic-bets')
        expect(quadrantFor('Low', 'quick')).toBe('fill-ins')
        expect(quadrantFor('Low', 'long')).toBe('deprioritise')
    })

    it('returns null for center-axis cells (Medium row + Medium column)', () => {
        expect(quadrantFor('Medium', 'quick')).toBeNull()
        expect(quadrantFor('Medium', 'medium')).toBeNull()
        expect(quadrantFor('Medium', 'long')).toBeNull()
        expect(quadrantFor('High', 'medium')).toBeNull()
        expect(quadrantFor('Low', 'medium')).toBeNull()
    })
})

describe('buildQuickWinsMatrixLayout — bucketing', () => {
    it('emits a 3×3 grid', () => {
        const layout = buildQuickWinsMatrixLayout([])
        expect(layout.cells.length).toBe(3)
        for (const row of layout.cells) expect(row.length).toBe(3)
    })

    it('routes High × Quick into top-left (quick-wins)', () => {
        const layout = buildQuickWinsMatrixLayout([make({})])
        expect(layout.cells[0][0].quadrant).toBe('quick-wins')
        expect(layout.cells[0][0].opportunityIndices).toEqual([0])
    })

    it('routes High × Long into top-right (strategic-bets)', () => {
        const layout = buildQuickWinsMatrixLayout([make({ timeline: 'Long-term (9+ months)' })])
        expect(layout.cells[0][2].quadrant).toBe('strategic-bets')
        expect(layout.cells[0][2].opportunityIndices).toEqual([0])
    })

    it('routes Low × Quick into bottom-left (fill-ins)', () => {
        const layout = buildQuickWinsMatrixLayout([
            make({ impact_rating: 'Low', timeline: 'Quick Win (1-3 months)' }),
        ])
        expect(layout.cells[2][0].quadrant).toBe('fill-ins')
        expect(layout.cells[2][0].opportunityIndices).toEqual([0])
    })

    it('routes Low × Long into bottom-right (deprioritise)', () => {
        const layout = buildQuickWinsMatrixLayout([
            make({ impact_rating: 'Low', timeline: 'Long-term (9+ months)' }),
        ])
        expect(layout.cells[2][2].quadrant).toBe('deprioritise')
        expect(layout.cells[2][2].opportunityIndices).toEqual([0])
    })

    it('routes unrecognised timeline into the Medium-term column', () => {
        // Suppress the dev warning during this test so it doesn't
        // pollute the test output.
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
        const layout = buildQuickWinsMatrixLayout([make({ impact_rating: 'High', timeline: 'Unspecified' })])
        expect(layout.cells[0][1].opportunityIndices).toEqual([0])
        warnSpy.mockRestore()
    })

    it('groups multiple opportunities into the same cell', () => {
        const opps = [
            make({ impact_rating: 'High', timeline: 'Quick Win' }),
            make({ impact_rating: 'High', timeline: 'Quick Win' }),
            make({ impact_rating: 'High', timeline: 'Quick Win' }),
        ]
        const layout = buildQuickWinsMatrixLayout(opps)
        expect(layout.cells[0][0].opportunityIndices).toEqual([0, 1, 2])
    })
})

describe('buildQuickWinsMatrixLayout — sort order', () => {
    it('sorts in-cell opportunities by strategic_category then by index', () => {
        const opps = [
            make({ strategic_category: 'Z-cat' }), // index 0
            make({ strategic_category: 'A-cat' }), // index 1
            make({ strategic_category: 'M-cat' }), // index 2
            make({ strategic_category: 'A-cat' }), // index 3 — tie with index 1
        ]
        const layout = buildQuickWinsMatrixLayout(opps)
        // All four land in High × Quick. Expected sort:
        // (A-cat, 1), (A-cat, 3), (M-cat, 2), (Z-cat, 0)
        expect(layout.cells[0][0].opportunityIndices).toEqual([1, 3, 2, 0])
    })
})

describe('buildQuickWinsMatrixLayout — coordinates', () => {
    it('every cell carries its impact + timeline coordinates', () => {
        const layout = buildQuickWinsMatrixLayout([])
        const impactOrder = ['High', 'Medium', 'Low'] as const
        const timelineOrder = ['quick', 'medium', 'long'] as const
        for (let r = 0; r < 3; r += 1) {
            for (let c = 0; c < 3; c += 1) {
                expect(layout.cells[r][c].impact).toBe(impactOrder[r])
                expect(layout.cells[r][c].timeline).toBe(timelineOrder[c])
            }
        }
    })
})
