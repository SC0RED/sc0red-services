import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import PrintEbitdaOutline from '@/components/print/PrintEbitdaOutline'
import { sortOpportunities } from '@/lib/pdf/sortOpportunities'
import type { EbitdaNode, EbitdaTree, Opportunity } from '@/lib/types/api'

const opp = (overrides: Partial<Opportunity>): Opportunity => ({
    title: 'untitled',
    description: 'd',
    impact_rating: 'High',
    timeline: 't',
    strategic_category: 'Operational Efficiency',
    ...overrides,
})

const sampleOpportunities: Opportunity[] = [
    opp({ title: 'Reduce support cost' }),
    opp({ title: 'Up-sell automation' }),
]
const sortedOpportunities = sortOpportunities(sampleOpportunities)

const node = (overrides: Partial<EbitdaNode>): EbitdaNode => ({
    id: 'node',
    label: 'Node',
    type: 'subtotal',
    description: '',
    linked_opportunity_indices: [],
    ...overrides,
})

const smallTree: EbitdaTree = {
    treeData: [
        node({
            id: 'root',
            label: 'Operating Revenue',
            type: 'revenue',
            value_range: '$10M-$15M',
            children: [
                node({
                    id: 'sub-1',
                    label: 'Subscriptions',
                    type: 'revenue',
                    value_range: '$8M',
                    linked_opportunity_indices: [1],
                }),
            ],
        }),
    ],
}

describe('PrintEbitdaOutline', () => {
    it('renders the section heading and outline mode marker', () => {
        const { container } = render(
            <PrintEbitdaOutline ebitdaTree={smallTree} sortedOpportunities={sortedOpportunities} />
        )
        expect(screen.getByText('EBITDA Impact Model')).toBeInTheDocument()
        expect(container.querySelector('section[data-render-mode="outline"]')).not.toBeNull()
    })

    it('shows every node label regardless of depth', () => {
        render(<PrintEbitdaOutline ebitdaTree={smallTree} sortedOpportunities={sortedOpportunities} />)
        expect(screen.getByText('Operating Revenue')).toBeInTheDocument()
        expect(screen.getByText('Subscriptions')).toBeInTheDocument()
    })

    it('renders percentage_of_parent as the integer the backend emits (no x100 doubling)', () => {
        // Regression guard for the ``Math.round(... * 100)`` bug PR #327
        // introduced. The backend emits ``percentage_of_parent`` as an
        // integer 0–100 (validated in ``_apply_percentage``). Rendering
        // it via ``* 100`` produced "8000% of parent" for an 80% node;
        // the architecture-reviewer pass for redesign-analysis-visuals
        // P2 caught it because the test fixture had no
        // ``percentage_of_parent`` set and the bug was invisible.
        const treeWithPct: EbitdaTree = {
            treeData: [
                node({
                    id: 'root',
                    label: 'Operating Revenue',
                    type: 'revenue',
                    value_range: '$10M-$15M',
                    children: [
                        node({
                            id: 'sub-1',
                            label: 'Subscriptions',
                            type: 'revenue',
                            value_range: '$8M',
                            percentage_of_parent: 80,
                        }),
                    ],
                }),
            ],
        }
        render(<PrintEbitdaOutline ebitdaTree={treeWithPct} sortedOpportunities={sortedOpportunities} />)
        // Anti-bug: must NOT show "8000% of parent". Must show "80% of parent".
        expect(screen.getByText('80% of parent')).toBeInTheDocument()
        expect(screen.queryByText('8000% of parent')).toBeNull()
    })

    it('resolves linkage callouts to the printed-index opportunity title', () => {
        render(<PrintEbitdaOutline ebitdaTree={smallTree} sortedOpportunities={sortedOpportunities} />)
        // originalIndex 1 → "Up-sell automation" (still printedIndex 2 because
        // both opportunities are High and stable-sort preserves API order).
        expect(screen.getByText(/Up-sell automation/)).toBeInTheDocument()
    })

    it('renders very wide trees by recursing through every node', () => {
        const wideChildren: EbitdaNode[] = []
        for (let i = 0; i < 35; i++) {
            wideChildren.push(node({ id: `child-${i}`, label: `Child ${i}`, type: 'cost' }))
        }
        const wideTree: EbitdaTree = {
            treeData: [node({ id: 'root', label: 'Root', children: wideChildren })],
        }
        render(<PrintEbitdaOutline ebitdaTree={wideTree} sortedOpportunities={sortedOpportunities} />)
        expect(screen.getByText('Child 0')).toBeInTheDocument()
        expect(screen.getByText('Child 34')).toBeInTheDocument()
    })

    it('renders deep trees, indenting every level', () => {
        const deepTree: EbitdaTree = {
            treeData: [
                node({
                    id: 'd1',
                    label: 'd1',
                    children: [
                        node({
                            id: 'd2',
                            label: 'd2',
                            children: [
                                node({
                                    id: 'd3',
                                    label: 'd3',
                                    children: [
                                        node({
                                            id: 'd4',
                                            label: 'd4',
                                            children: [node({ id: 'd5', label: 'd5' })],
                                        }),
                                    ],
                                }),
                            ],
                        }),
                    ],
                }),
            ],
        }
        render(<PrintEbitdaOutline ebitdaTree={deepTree} sortedOpportunities={sortedOpportunities} />)
        for (const label of ['d1', 'd2', 'd3', 'd4', 'd5']) {
            expect(screen.getByText(label)).toBeInTheDocument()
        }
    })

    it('applies the .print-ebitda class so the page-break-inside: avoid rule kicks in', () => {
        // The class used to also activate an `@page ebitda-page { size:
        // A3 landscape }` override; that was removed when the
        // visualisation moved from ReactFlow tree to vertical indented
        // outline. The class survives as the shared selector for
        // `page-break-inside: avoid` in print.css.
        const { container } = render(
            <PrintEbitdaOutline ebitdaTree={smallTree} sortedOpportunities={sortedOpportunities} />
        )
        expect(container.querySelector('.print-ebitda')).not.toBeNull()
    })

    it('does NOT render the legacy confidence inline marker (removed in redesign-analysis-visuals P2)', () => {
        // Print parity follows screen: the confidence chip + inline
        // marker are gone. The data still flows on EbitdaNode for any
        // future surface, but no rendering here.
        const treeWithConfidence: EbitdaTree = {
            treeData: [
                node({
                    id: 'rev',
                    label: 'Revenue',
                    type: 'revenue',
                    value_range: '$10M',
                    confidence_level: 'high',
                    confidence_basis: 'Both inputs matched.',
                }),
                node({
                    id: 'rev2',
                    label: 'Other Revenue',
                    type: 'revenue',
                    value_range: '$2M',
                    confidence_level: 'medium',
                    confidence_basis: 'Partial signal.',
                }),
            ],
        }
        const { queryAllByTestId } = render(
            <PrintEbitdaOutline ebitdaTree={treeWithConfidence} sortedOpportunities={sortedOpportunities} />
        )
        expect(queryAllByTestId('ebitda-confidence-print')).toHaveLength(0)
    })

    it('omits the confidence marker when the node has no confidence level', () => {
        const treeNoConfidence: EbitdaTree = {
            treeData: [
                node({
                    id: 'rev',
                    label: 'Revenue',
                    type: 'revenue',
                    value_range: '$10M',
                    // No confidence_level
                }),
            ],
        }
        const { queryAllByTestId } = render(
            <PrintEbitdaOutline ebitdaTree={treeNoConfidence} sortedOpportunities={sortedOpportunities} />
        )
        expect(queryAllByTestId('ebitda-confidence-print')).toHaveLength(0)
    })
})
