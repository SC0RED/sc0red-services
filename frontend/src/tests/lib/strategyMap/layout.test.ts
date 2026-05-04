import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { BAND_HEIGHT, buildStrategyMapGraph } from '@/lib/strategyMap/layout'
import type { StrategyMap } from '@/lib/types/api'

import { fullStrategyMap } from '@/tests/components/strategy-map/_fixtures'

/**
 * Unit tests for the α′ layout algorithm.
 *
 * The fixture (`fullStrategyMap`) has two themes, so:
 *   - Theme 0 ("Grow Through Foodservice") supports F1
 *   - Theme 1 ("Deliver Convenience and Value") supports F1, F2
 *   - First-listed-theme-wins → F1 → column 0, F2 → column 1
 *   - F3 has no supports_financial → centre lane (null)
 *
 * Customer / Capacity placement is inferred from the fixture's arrows.
 */

const findNode = (graph: ReturnType<typeof buildStrategyMapGraph>, id: string) => {
    const node = graph.nodes.find((n) => n.id === id)
    if (!node) throw new Error(`fixture missing node ${id}`)
    return node
}

const findEdge = (graph: ReturnType<typeof buildStrategyMapGraph>, id: string) => {
    return graph.edges.find((e) => e.id === id)
}

const yOf = (graph: ReturnType<typeof buildStrategyMapGraph>, id: string) => findNode(graph, id).position.y

const xOf = (graph: ReturnType<typeof buildStrategyMapGraph>, id: string) => findNode(graph, id).position.x

describe('buildStrategyMapGraph — perspective row placement', () => {
    it('places financial chips on the top band, capacity on the bottom', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)

        const yFinancial = yOf(graph, 'F1')
        const yCustomer = yOf(graph, 'C1')
        const yInternal = yOf(graph, 'I1.1')
        const yCapacity = yOf(graph, 'O.P')

        expect(yFinancial).toBeLessThan(yCustomer)
        expect(yCustomer).toBeLessThan(yInternal)
        expect(yInternal).toBeLessThan(yCapacity)
    })

    it('separates bands by exactly BAND_HEIGHT', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)

        const yFinancial = yOf(graph, 'F1')
        const yCustomer = yOf(graph, 'C1')
        const yInternal = yOf(graph, 'I1.1')
        const yCapacity = yOf(graph, 'O.P')

        expect(yCustomer - yFinancial).toBe(BAND_HEIGHT)
        expect(yInternal - yCustomer).toBe(BAND_HEIGHT)
        expect(yCapacity - yInternal).toBe(BAND_HEIGHT)
    })
})

describe('buildStrategyMapGraph — financial column from supports_financial_objectives', () => {
    it('places F1 in column 0 (first theme that lists it)', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)
        // Both themes list F1, but first-listed wins → theme 0.
        expect(findNode(graph, 'F1').data.perspective).toBe('financial')
        expect(xOf(graph, 'F1')).toBe(0)
    })

    it('places F2 in column 1 (only listed by theme 1)', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)
        // F2 should be at column 1's base x. Slot offset 0 because F2 is
        // the only chip in (financial, column 1).
        expect(xOf(graph, 'F2')).toBeGreaterThan(xOf(graph, 'F1'))
    })

    it('places F3 in the centre lane (no theme lists it)', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)
        // Centre between column 0 and column 1 → x === COLUMN_WIDTH / 2 with two themes.
        const xF3 = xOf(graph, 'F3')
        expect(xF3).toBeGreaterThan(xOf(graph, 'F1'))
        expect(xF3).toBeLessThan(xOf(graph, 'F2'))
    })
})

describe('buildStrategyMapGraph — internal-process column from theme nesting', () => {
    it('places I1.1 in column 0 (theme 0)', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)
        expect(xOf(graph, 'I1.1')).toBe(0)
    })

    it('places I2.1 in column 1 (theme 1)', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)
        expect(xOf(graph, 'I2.1')).toBeGreaterThan(xOf(graph, 'I1.1'))
    })
})

describe('buildStrategyMapGraph — customer column inferred from outbound arrow', () => {
    it('places C1 in column of F1 (C1 → F1 arrow exists)', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)
        // The fixture has `{ from: 'C1', to: 'F1' }`. F1 sits at column 0.
        expect(xOf(graph, 'C1')).toBe(xOf(graph, 'F1'))
    })

    it('falls back to centre lane when customer chip has no disambiguating arrow', () => {
        // Construct a minimal fixture: C-only objective without any arrow
        // pointing to or from it.
        const sparseMap: StrategyMap = {
            ...fullStrategyMap,
            customer: {
                objectives: [
                    {
                        id: 'C9',
                        title: 'Orphan customer obj with no arrows',
                        definition:
                            'A customer objective with no inbound or outbound arrow — should land in the centre lane.',
                        panel: 'consumer',
                        confidence: 'LOW',
                    },
                    ...fullStrategyMap.customer.objectives,
                ],
            },
        }
        const graph = buildStrategyMapGraph(sparseMap)
        const xC9 = xOf(graph, 'C9')
        // Centre is between column 0 and column 1 → strictly between F1 and F2.
        expect(xC9).toBeGreaterThan(xOf(graph, 'F1'))
        expect(xC9).toBeLessThan(xOf(graph, 'F2'))
    })
})

describe('buildStrategyMapGraph — capacity column inference and triad fallback', () => {
    it('places O.P in column of I1.1 (O.P → I1.1 arrow exists)', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)
        // The fixture has `{ from: 'O.P', to: 'I1.1' }`. I1.1 sits at column 0.
        expect(xOf(graph, 'O.P')).toBe(xOf(graph, 'I1.1'))
    })

    it('places O.T in column of I2.1 (O.T → I2.1 arrow exists)', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)
        expect(xOf(graph, 'O.T')).toBe(xOf(graph, 'I2.1'))
    })

    it('spreads the People/Tech/Culture triad when arrows are sparse', () => {
        // Strip ALL arrows so capacity has no inference signal. With 2
        // themes, fallback puts People at column 0, Technology at the
        // centre, Culture at column 1.
        const noArrowsMap: StrategyMap = { ...fullStrategyMap, arrows: [] }
        const graph = buildStrategyMapGraph(noArrowsMap)

        const xP = xOf(graph, 'O.P')
        const xT = xOf(graph, 'O.T')
        const xC = xOf(graph, 'O.C')

        // Triad should NOT collapse — three distinct x positions.
        expect(new Set([xP, xT, xC]).size).toBe(3)
        expect(xP).toBeLessThan(xT)
        expect(xT).toBeLessThan(xC)
    })
})

describe('buildStrategyMapGraph — arrow validation', () => {
    let warnSpy: ReturnType<typeof vi.spyOn>

    beforeEach(() => {
        warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    })

    afterEach(() => {
        warnSpy.mockRestore()
    })

    it('builds an edge for every valid arrow', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)
        // The fixture has 5 arrows, all referencing valid IDs.
        expect(graph.edges).toHaveLength(fullStrategyMap.arrows.length)
        expect(findEdge(graph, 'O.P__I1.1')).toBeDefined()
        expect(findEdge(graph, 'C1__F1')).toBeDefined()
    })

    it('preserves the hypothesis text on each edge', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)
        const edge = findEdge(graph, 'I1.1__C1')
        expect(edge?.data?.hypothesis).toContain('Signature food platforms')
    })

    it('drops an arrow whose `from` references an unknown chip', () => {
        const mapWithBadArrow: StrategyMap = {
            ...fullStrategyMap,
            arrows: [
                ...fullStrategyMap.arrows,
                {
                    from: 'F999',
                    to: 'C1',
                    hypothesis: 'A made-up source ID — should not produce an edge.',
                },
            ],
        }
        const graph = buildStrategyMapGraph(mapWithBadArrow)
        expect(findEdge(graph, 'F999__C1')).toBeUndefined()
        // Other arrows still produce edges.
        expect(graph.edges).toHaveLength(fullStrategyMap.arrows.length)
        expect(warnSpy).toHaveBeenCalledWith(
            expect.stringContaining('Dropping arrow with unknown endpoint(s): F999 → C1')
        )
    })

    it('drops an arrow whose `to` references an unknown chip', () => {
        const mapWithBadArrow: StrategyMap = {
            ...fullStrategyMap,
            arrows: [
                {
                    from: 'F1',
                    to: 'Z9',
                    hypothesis: 'Pointing nowhere.',
                },
            ],
        }
        const graph = buildStrategyMapGraph(mapWithBadArrow)
        expect(graph.edges).toHaveLength(0)
        expect(warnSpy).toHaveBeenCalledOnce()
    })
})

describe('buildStrategyMapGraph — node data shape', () => {
    it('marks customer chips with customerVoice=true and others false', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)
        expect(findNode(graph, 'C1').data.customerVoice).toBe(true)
        expect(findNode(graph, 'F1').data.customerVoice).toBe(false)
        expect(findNode(graph, 'I1.1').data.customerVoice).toBe(false)
        expect(findNode(graph, 'O.P').data.customerVoice).toBe(false)
    })

    it('tags each capacity chip with its bucket', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)
        expect(findNode(graph, 'O.P').data.capacityBucket).toBe('People')
        expect(findNode(graph, 'O.T').data.capacityBucket).toBe('Technology')
        expect(findNode(graph, 'O.C').data.capacityBucket).toBe('Culture')
    })

    it('passes through definition, confidence, and rationaleSource (or null)', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)
        const f1 = findNode(graph, 'F1').data
        expect(f1.definition).toContain('grow same-segment revenue')
        expect(f1.confidence).toBe('HIGH')
        // Fixture doesn't set rationale_source, so it should be null.
        expect(f1.rationaleSource).toBeNull()
    })

    it('every node has type "strategyMap"', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)
        for (const node of graph.nodes) {
            expect(node.type).toBe('strategyMap')
        }
    })

    it('every node is non-draggable + selectable (allows tap-to-focus on touch)', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)
        for (const node of graph.nodes) {
            expect(node.draggable).toBe(false)
            expect(node.selectable).toBe(true)
        }
    })
})

describe('buildStrategyMapGraph — degenerate inputs', () => {
    it('handles a single-theme strategy map (all chips in column 0)', () => {
        const oneThemeMap: StrategyMap = {
            ...fullStrategyMap,
            internalProcesses: {
                themes: [fullStrategyMap.internalProcesses.themes[0]],
            },
            // Drop F2/F3 since their themes no longer exist.
            financial: {
                objectives: [fullStrategyMap.financial.objectives[0]],
            },
        }
        const graph = buildStrategyMapGraph(oneThemeMap)
        // F1 should still get column 0; chip survived.
        expect(findNode(graph, 'F1')).toBeDefined()
        expect(xOf(graph, 'F1')).toBe(0)
    })

    it('handles an arrow-free strategy map without throwing', () => {
        const noArrowsMap: StrategyMap = { ...fullStrategyMap, arrows: [] }
        const graph = buildStrategyMapGraph(noArrowsMap)
        expect(graph.edges).toHaveLength(0)
        // Customers fall back to the centre lane (no arrows).
        const xC1 = xOf(graph, 'C1')
        expect(xC1).toBeGreaterThan(xOf(graph, 'F1'))
    })
})
