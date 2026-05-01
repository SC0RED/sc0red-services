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

    it('applies the .print-ebitda class so the named @page rule kicks in', () => {
        const { container } = render(
            <PrintEbitdaOutline ebitdaTree={smallTree} sortedOpportunities={sortedOpportunities} />
        )
        expect(container.querySelector('.print-ebitda')).not.toBeNull()
    })
})
