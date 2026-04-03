import { describe, it, expect, vi } from 'vitest'

import { flattenNodes } from '@/components/EbitdaTree'
import type { EbitdaNode } from '@/lib/types/api'

// ReactFlow requires browser APIs not available in jsdom,
// so we test the exported flattenNodes utility and type structures.
// The full component is dynamically imported with ssr:false in the page.

// Mock ResizeObserver for any component that might need it
global.ResizeObserver = vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
}))

const SAMPLE_TREE: EbitdaNode[] = [
    {
        id: 'revenue',
        label: 'Total Revenue',
        type: 'revenue',
        value_range: '$10M-$50M',
        parent_id: null,
        description: 'All revenue streams',
        linked_opportunity_indices: [],
        children: [
            {
                id: 'subscriptions',
                label: 'Subscriptions',
                type: 'revenue',
                value_range: '$8M-$40M',
                percentage_of_parent: 80,
                parent_id: 'revenue',
                description: 'SaaS subscriptions',
                linked_opportunity_indices: [0],
                children: [],
            },
            {
                id: 'services',
                label: 'Services',
                type: 'revenue',
                value_range: '$2M-$10M',
                percentage_of_parent: 20,
                parent_id: 'revenue',
                description: 'Professional services',
                linked_opportunity_indices: [],
                children: [],
            },
        ],
    },
    {
        id: 'ebitda',
        label: 'EBITDA',
        type: 'subtotal',
        value_range: '$2M-$8M',
        parent_id: null,
        description: 'Earnings before interest, taxes, depreciation and amortisation',
        linked_opportunity_indices: [0, 1],
        children: [],
    },
]

describe('flattenNodes', () => {
    it('flattens a nested tree into a flat list', () => {
        const flat = flattenNodes(SAMPLE_TREE)
        expect(flat).toHaveLength(4) // revenue, subscriptions, services, ebitda
    })

    it('preserves node properties', () => {
        const flat = flattenNodes(SAMPLE_TREE)
        const revenue = flat.find((n) => n.id === 'revenue')
        expect(revenue).toBeDefined()
        expect(revenue!.label).toBe('Total Revenue')
        expect(revenue!.type).toBe('revenue')
        expect(revenue!.value_range).toBe('$10M-$50M')
    })

    it('assigns parent_id from parent context', () => {
        const flat = flattenNodes(SAMPLE_TREE)
        const subs = flat.find((n) => n.id === 'subscriptions')
        expect(subs).toBeDefined()
        expect(subs!.parent_id).toBe('revenue')
    })

    it('top-level nodes have null parent_id', () => {
        const flat = flattenNodes(SAMPLE_TREE)
        const revenue = flat.find((n) => n.id === 'revenue')
        expect(revenue!.parent_id).toBeNull()
    })

    it('preserves linked_opportunity_indices', () => {
        const flat = flattenNodes(SAMPLE_TREE)
        const ebitda = flat.find((n) => n.id === 'ebitda')
        expect(ebitda!.linked_opportunity_indices).toEqual([0, 1])
    })

    it('handles empty tree', () => {
        const flat = flattenNodes([])
        expect(flat).toHaveLength(0)
    })

    it('handles deeply nested trees', () => {
        const deep: EbitdaNode[] = [
            {
                id: 'a',
                label: 'A',
                type: 'revenue',
                parent_id: null,
                description: '',
                linked_opportunity_indices: [],
                children: [
                    {
                        id: 'b',
                        label: 'B',
                        type: 'revenue',
                        parent_id: 'a',
                        description: '',
                        linked_opportunity_indices: [],
                        children: [
                            {
                                id: 'c',
                                label: 'C',
                                type: 'cost',
                                parent_id: 'b',
                                description: '',
                                linked_opportunity_indices: [0],
                                children: [],
                            },
                        ],
                    },
                ],
            },
        ]
        const flat = flattenNodes(deep)
        expect(flat).toHaveLength(3)
        expect(flat[2].id).toBe('c')
        expect(flat[2].parent_id).toBe('b')
    })
})
