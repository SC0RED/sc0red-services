import { describe, it, expect } from 'vitest'

import { PERSPECTIVE_ROW_ORDER, buildStrategyMapLayout, firstSentence } from '@/lib/utils/strategyMapLayout'
import { fullStrategyMap } from '@/tests/components/strategy-map/_fixtures'

/**
 * Unit tests for the pure Balanced-Scorecard layout helper introduced
 * in P6 of ``redesign-analysis-visuals``. The helper has no React
 * dependency, so these tests run on the raw data shape only.
 */

const rowIndex = {
    financial: PERSPECTIVE_ROW_ORDER.indexOf('financial'),
    customer: PERSPECTIVE_ROW_ORDER.indexOf('customer'),
    internal: PERSPECTIVE_ROW_ORDER.indexOf('internal'),
    capacity: PERSPECTIVE_ROW_ORDER.indexOf('capacity'),
}

describe('buildStrategyMapLayout — perspectives and themes', () => {
    it('emits one column per internal-process theme in declaration order', () => {
        const layout = buildStrategyMapLayout(fullStrategyMap)
        expect(layout.themeNames).toEqual(['Grow Through Foodservice', 'Deliver Convenience and Value'])
    })

    it('emits 4 perspective rows × N theme columns', () => {
        const layout = buildStrategyMapLayout(fullStrategyMap)
        expect(layout.cells.length).toBe(4)
        for (const row of layout.cells) {
            expect(row.length).toBe(layout.themeNames.length)
        }
    })

    it('routes a financial objective into the theme that claims it', () => {
        // Fixture: theme 0 ("Grow Through Foodservice") claims F1.
        const layout = buildStrategyMapLayout(fullStrategyMap)
        const financialRow = layout.cells[rowIndex.financial]
        const f1Cell = financialRow[0]
        expect(f1Cell.objectives.map((o) => o.objective.id)).toContain('F1')
    })

    it('routes a financial objective with NO claiming theme into column 0 as fallback', () => {
        // F3 is not in any theme's supports_financial_objectives list.
        const layout = buildStrategyMapLayout(fullStrategyMap)
        const financialRow = layout.cells[rowIndex.financial]
        const ids = financialRow[0].objectives.map((o) => o.objective.id)
        expect(ids).toContain('F3')
    })

    it('round-robins customer objectives across theme columns', () => {
        // 3 customer objectives, 2 columns → col 0 gets C1, C3; col 1 gets C2.
        const layout = buildStrategyMapLayout(fullStrategyMap)
        const customerRow = layout.cells[rowIndex.customer]
        const col0Ids = customerRow[0].objectives.map((o) => o.objective.id)
        const col1Ids = customerRow[1].objectives.map((o) => o.objective.id)
        expect(col0Ids).toEqual(['C1', 'C3'])
        expect(col1Ids).toEqual(['C2'])
    })

    it("places each theme's internal-process objectives in its own column", () => {
        const layout = buildStrategyMapLayout(fullStrategyMap)
        const internalRow = layout.cells[rowIndex.internal]
        expect(internalRow[0].objectives.map((o) => o.objective.id)).toEqual(['I1.1'])
        expect(internalRow[1].objectives.map((o) => o.objective.id)).toEqual(['I2.1'])
    })

    it('round-robins capacity (people/tech/culture) across theme columns', () => {
        // 3 capacity objectives, 2 columns → col 0: People, Culture; col 1: Technology.
        const layout = buildStrategyMapLayout(fullStrategyMap)
        const capacityRow = layout.cells[rowIndex.capacity]
        const col0 = capacityRow[0].objectives.map((o) => (o.kind === 'capacity' ? o.subkind : null))
        const col1 = capacityRow[1].objectives.map((o) => (o.kind === 'capacity' ? o.subkind : null))
        expect(col0).toEqual(['people', 'culture'])
        expect(col1).toEqual(['technology'])
    })

    it('preserves the cell perspective + themeIndex coordinates on every cell', () => {
        const layout = buildStrategyMapLayout(fullStrategyMap)
        for (let r = 0; r < layout.cells.length; r += 1) {
            for (let c = 0; c < layout.cells[r].length; c += 1) {
                const cell = layout.cells[r][c]
                expect(cell.perspective).toBe(PERSPECTIVE_ROW_ORDER[r])
                expect(cell.themeIndex).toBe(c)
            }
        }
    })

    it('handles strategy maps with zero themes without throwing', () => {
        // Pathological but valid: capacity/customer round-robin would
        // divide by zero. The helper short-circuits.
        const empty = {
            ...fullStrategyMap,
            internalProcesses: { themes: [] },
        }
        const layout = buildStrategyMapLayout(empty)
        expect(layout.themeNames).toEqual([])
        expect(layout.cells.length).toBe(4)
        for (const row of layout.cells) {
            expect(row.length).toBe(0)
        }
    })
})

describe('firstSentence', () => {
    it('returns the substring up to and including the first terminator', () => {
        expect(firstSentence('Hello world. More text follows.')).toBe('Hello world.')
        expect(firstSentence('Question? Answer.')).toBe('Question?')
        expect(firstSentence('Surprise! Continued.')).toBe('Surprise!')
    })

    it('falls back to the full text when no terminator is present', () => {
        expect(firstSentence('No terminator here')).toBe('No terminator here')
    })

    it('returns an empty string for blank input', () => {
        expect(firstSentence('   ')).toBe('')
        expect(firstSentence('')).toBe('')
    })

    it('requires whitespace AFTER the terminator (no-space periods fall through)', () => {
        // The regex demands ``[.!?](?:\s|$)`` so a period immediately
        // followed by a non-whitespace character (the "Inc.last" case)
        // is rejected as a sentence boundary. When no terminator
        // satisfies the rule the helper falls back to the full text —
        // mirrors the behaviour for definitions with no punctuation at
        // all and keeps the cell readable rather than truncated mid-word.
        const input = 'Acquired Acme Inc.last quarter, then grew'
        expect(firstSentence(input)).toBe(input)
    })
})
