import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { BAND_HEIGHT, COLUMN_WIDTH, SLOT_Y_OFFSET, buildStrategyMapGraph } from '@/lib/strategyMap/layout'
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

    it('places F3 in the shared lane past the last real column', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)
        // Shared-lane chips sit at x = totalColumns * COLUMN_WIDTH (one
        // virtual column past the last real theme column). For the
        // 2-theme fixture, that's x = 2 * COLUMN_WIDTH = 560 — to the
        // right of F2 (column 1, x = COLUMN_WIDTH = 280).
        const xF3 = xOf(graph, 'F3')
        expect(xF3).toBe(2 * COLUMN_WIDTH)
        expect(xF3).toBeGreaterThan(xOf(graph, 'F2'))
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

    it('falls back to shared lane (past last column) when customer chip has no disambiguating arrow', () => {
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
                            'A customer objective with no inbound or outbound arrow — should land in the shared lane.',
                        panel: 'consumer',
                        confidence: 'LOW',
                    },
                    ...fullStrategyMap.customer.objectives,
                ],
            },
        }
        const graph = buildStrategyMapGraph(sparseMap)
        // Shared lane is past the last real column (totalColumns *
        // COLUMN_WIDTH). For 2 themes that's x = 560.
        expect(xOf(graph, 'C9')).toBe(2 * COLUMN_WIDTH)
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
        // themes, the fallback assigns People=col 0, Technology=null
        // (shared lane → x = 2 * COLUMN_WIDTH = 560), Culture=col 1
        // (x = COLUMN_WIDTH = 280). All three land at distinct x.
        const noArrowsMap: StrategyMap = { ...fullStrategyMap, arrows: [] }
        const graph = buildStrategyMapGraph(noArrowsMap)

        const xP = xOf(graph, 'O.P')
        const xT = xOf(graph, 'O.T')
        const xC = xOf(graph, 'O.C')

        // Triad should NOT collapse — three distinct x positions.
        expect(new Set([xP, xT, xC]).size).toBe(3)
        // Order: P < C < T (Technology lands in the shared lane past
        // the last column when arrows are sparse — the fallback hasn't
        // changed semantically, but the shared-lane x is now to the
        // right of all real columns rather than between them).
        expect(xP).toBe(0)
        expect(xC).toBe(COLUMN_WIDTH)
        expect(xT).toBe(2 * COLUMN_WIDTH)
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

    it('flags chips in the centre lane with inSharedLane=true (and others false)', () => {
        const graph = buildStrategyMapGraph(fullStrategyMap)
        // F3 is unanchored in the fixture (no theme lists it) → centre lane.
        expect(findNode(graph, 'F3').data.inSharedLane).toBe(true)
        // Anchored chips: not in shared lane.
        expect(findNode(graph, 'F1').data.inSharedLane).toBe(false)
        expect(findNode(graph, 'I1.1').data.inSharedLane).toBe(false)
        expect(findNode(graph, 'C1').data.inSharedLane).toBe(false)
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

// ── Regression tests for bugs surfaced in production screenshot ───────────

describe('buildStrategyMapGraph — vertical slot stacking (production bug regression)', () => {
    /**
     * Earlier versions stacked slots horizontally with a per-slot x-offset
     * (slot N at x = column*COLUMN_WIDTH + N * (SLOT_WIDTH + SLOT_GAP)).
     * With CHIP_WIDTH=220 and COLUMN_WIDTH=280 the slot-1 chip extended
     * past the column boundary and overlapped the next column's chip
     * visually. Fixed by stacking slots vertically inside the band
     * (y += slot * SLOT_Y_OFFSET).
     *
     * The fixture's themes have one IP objective each, so this test
     * synthesises a multi-objective theme to exercise the path.
     */
    it('stacks slot-1 chips below slot-0 chips at the same x (not to the right)', () => {
        const multiSlotMap: StrategyMap = {
            ...fullStrategyMap,
            internalProcesses: {
                themes: [
                    {
                        ...fullStrategyMap.internalProcesses.themes[0],
                        objectives: [
                            ...fullStrategyMap.internalProcesses.themes[0].objectives,
                            {
                                id: 'I1.2',
                                title: 'Second objective in the same theme',
                                definition:
                                    'Forced into slot 1 of theme 0 to exercise the vertical-stacking layout path.',
                                category: 'innovation',
                                confidence: 'MEDIUM',
                            },
                        ],
                    },
                    fullStrategyMap.internalProcesses.themes[1],
                ],
            },
        }
        const graph = buildStrategyMapGraph(multiSlotMap)
        // I1.1 (slot 0) and I1.2 (slot 1) MUST share the same x — no
        // horizontal overflow into theme 1's column.
        expect(xOf(graph, 'I1.2')).toBe(xOf(graph, 'I1.1'))
        // I1.2 sits one slot below I1.1.
        expect(yOf(graph, 'I1.2')).toBe(yOf(graph, 'I1.1') + SLOT_Y_OFFSET)
    })
})

describe('buildStrategyMapGraph — shared-lane never collides with a real column', () => {
    /**
     * Production screenshot: a 3-theme strategy map placed a centre-lane
     * customer chip (C2) at x = COLUMN_WIDTH = 280, which is exactly
     * column 1's position — the chip stacked behind C4 (also column 1).
     * Fixed by offsetting the centre lane to a between-column position
     * when totalColumns is odd.
     */
    it('never coincides with a column position for any reasonable column count', () => {
        // Walk 1..6 themes and assert centre-lane x never equals any
        // real column's x.
        for (let totalColumns = 2; totalColumns <= 6; totalColumns++) {
            const themes = Array.from({ length: totalColumns }, (_, i) => ({
                name: `Theme ${i + 1}`,
                supports_financial_objectives: ['F1'],
                objectives: [
                    {
                        id: `I${i + 1}.1`,
                        title: `Theme-${i + 1} objective`,
                        definition: 'Long enough definition string to satisfy any min-length constraints.',
                        category: 'innovation' as const,
                        confidence: 'MEDIUM' as const,
                    },
                ],
            }))
            const map: StrategyMap = {
                ...fullStrategyMap,
                strategicPriorities: themes.map((t) => ({
                    name: t.name,
                    result: 'Some result string long enough to satisfy validation.',
                })),
                internalProcesses: { themes },
                financial: {
                    objectives: [
                        // F2 has no theme support → centre lane.
                        ...fullStrategyMap.financial.objectives,
                    ],
                },
            }
            const graph = buildStrategyMapGraph(map)
            const xF3 = xOf(graph, 'F3') // F3 is in shared lane in fixture
            for (let column = 0; column < totalColumns; column++) {
                expect(
                    xF3,
                    `centre-lane collided with column ${column} for totalColumns=${totalColumns}`
                ).not.toBe(column * COLUMN_WIDTH)
            }
        }
    })

    it('places shared-lane chips past the last column for 3-theme analyses (production bug)', () => {
        const threeThemeMap: StrategyMap = {
            ...fullStrategyMap,
            strategicPriorities: [
                { name: 'Priority A', result: 'A long enough result string for validation.' },
                { name: 'Priority B', result: 'A long enough result string for validation.' },
                { name: 'Priority C', result: 'A long enough result string for validation.' },
            ],
            internalProcesses: {
                themes: [
                    {
                        ...fullStrategyMap.internalProcesses.themes[0],
                        supports_financial_objectives: ['F1'],
                    },
                    {
                        ...fullStrategyMap.internalProcesses.themes[1],
                        supports_financial_objectives: ['F2'],
                    },
                    {
                        name: 'Theme 3',
                        supports_financial_objectives: [],
                        objectives: [
                            {
                                id: 'I3.1',
                                title: 'Theme 3 objective',
                                definition:
                                    'Long enough definition string to satisfy any min-length constraints.',
                                category: 'innovation',
                                confidence: 'MEDIUM',
                            },
                        ],
                    },
                ],
            },
        }
        const graph = buildStrategyMapGraph(threeThemeMap)
        // F3 has no theme anchor → shared lane. With totalColumns=3,
        // shared lane lands at x = 3 * COLUMN_WIDTH (one virtual column
        // past the last real column at x = 2 * COLUMN_WIDTH).
        const xF3 = xOf(graph, 'F3')
        expect(xF3).toBe(3 * COLUMN_WIDTH)
        // And it must NOT collide with any of the three real columns
        // (0, COLUMN_WIDTH, 2*COLUMN_WIDTH) — the production bug.
        expect(xF3).not.toBe(0)
        expect(xF3).not.toBe(COLUMN_WIDTH)
        expect(xF3).not.toBe(2 * COLUMN_WIDTH)
    })

    /**
     * Real-world bug: with 3 themes a customer chip without a
     * disambiguating arrow (e.g. C4 in the screenshot) landed at the
     * geometric centre of column 0 and column 1 (x ≈ 140). The chip is
     * 220 px wide so it physically overlapped C1 (column 0, spans 0-220).
     * This test reproduces the exact bug shape — 3 themes, customer chip
     * with no arrow — and asserts the chip lands clear of every real
     * column AND clear of the chip range of every neighbouring column
     * chip (0 ± CHIP_WIDTH).
     */
    it('shared-lane chip cannot horizontally overlap any real-column chip with 3 themes', () => {
        const threeThemes = [
            { name: 'Theme A', supports: ['F1'] },
            { name: 'Theme B', supports: ['F2'] },
            { name: 'Theme C', supports: ['F3'] },
        ]
        const productionShapeMap: StrategyMap = {
            ...fullStrategyMap,
            strategicPriorities: threeThemes.map((t) => ({
                name: t.name,
                result: 'A long enough result string for validation purposes.',
            })),
            internalProcesses: {
                themes: threeThemes.map((t, i) => ({
                    name: t.name,
                    supports_financial_objectives: t.supports,
                    objectives: [
                        {
                            id: `I${i + 1}.1`,
                            title: `${t.name} objective`,
                            definition:
                                'A long enough definition string to satisfy any min-length constraints.',
                            category: 'innovation' as const,
                            confidence: 'MEDIUM' as const,
                        },
                    ],
                })),
            },
            // C-orphan with no inbound or outbound arrow — production
            // example was "Connect me directly with…".
            customer: {
                objectives: [
                    {
                        id: 'C9',
                        title: 'Orphan customer chip with no inbound/outbound arrow',
                        definition:
                            'Has no arrow connecting it to financial or internal-process chips, so it falls through to the shared-lane fallback.',
                        panel: 'consumer',
                        confidence: 'LOW',
                    },
                    ...fullStrategyMap.customer.objectives,
                ],
            },
            arrows: [], // strip arrows so customer falls back deterministically
        }
        const graph = buildStrategyMapGraph(productionShapeMap)
        const xC9 = xOf(graph, 'C9')

        // C9 must land at x = 3 * COLUMN_WIDTH = 840 (past the last
        // real column at x = 560).
        expect(xC9).toBe(3 * COLUMN_WIDTH)

        // And — critical — it must not overlap any real column's chip.
        // A chip at column N spans `[N * COLUMN_WIDTH, N * COLUMN_WIDTH + CHIP_WIDTH]`.
        // Two chips overlap when their x-ranges intersect.
        const CHIP_WIDTH = 220
        for (let column = 0; column < 3; column++) {
            const columnChipStart = column * COLUMN_WIDTH
            const columnChipEnd = columnChipStart + CHIP_WIDTH
            const c9Start = xC9
            const c9End = xC9 + CHIP_WIDTH
            // Either C9 fully right of the column chip, or fully left.
            const noOverlap = c9Start >= columnChipEnd || c9End <= columnChipStart
            expect(
                noOverlap,
                `C9 [${c9Start},${c9End}] overlaps column ${column} [${columnChipStart},${columnChipEnd}]`
            ).toBe(true)
        }
    })
})
