import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'

import type { EbitdaTree, Opportunity } from '@/lib/types/api'

// Mock the dynamically imported EbitdaTree component
vi.mock('@/components/EbitdaTree', () => ({
    default: ({ treeData }: { treeData: unknown[] }) => (
        <div data-testid="ebitda-tree">nodes: {treeData.length}</div>
    ),
}))

// Import after mock
import EbitdaSection from '@/components/analysis/EbitdaSection'

const SAMPLE_TREE: EbitdaTree = {
    treeData: [
        {
            id: 'rev',
            label: 'Revenue',
            type: 'revenue',
            value_range: '$10M',
            parent_id: null,
            description: 'Total revenue',
            linked_opportunity_indices: [],
        },
    ],
    revenueEstimate: '$10M-$50M',
    ebitdaEstimate: '$2M-$8M',
    businessModelSummary: 'SaaS business model with recurring revenue',
}

const SAMPLE_OPPORTUNITIES: Opportunity[] = [
    {
        title: 'Test Opp',
        description: 'desc',
        impact_rating: 'High',
        timeline: '6m',
        strategic_category: 'Revenue Capture',
    },
]

describe('EbitdaSection', () => {
    it('does NOT render an internal "EBITDA Impact Model" heading (page-level wrapper owns it)', () => {
        // Per analysis-detail-consistency-wrapper D3, the heading +
        // its `<HelpTooltip term="ebitda_tree" />` adornment are
        // rendered at the page level by `AnalysisSection`. The leaf
        // renders only the body (badges + business-model summary +
        // tree).
        render(<EbitdaSection ebitdaTree={SAMPLE_TREE} opportunities={SAMPLE_OPPORTUNITIES} />)
        expect(screen.queryByText('EBITDA Impact Model')).toBeNull()
    })

    it('renders revenue and EBITDA badges', () => {
        render(<EbitdaSection ebitdaTree={SAMPLE_TREE} opportunities={SAMPLE_OPPORTUNITIES} />)
        expect(screen.getByText('Revenue: $10M-$50M')).toBeInTheDocument()
        expect(screen.getByText('EBITDA: $2M-$8M')).toBeInTheDocument()
    })

    it('renders business model summary', () => {
        render(<EbitdaSection ebitdaTree={SAMPLE_TREE} opportunities={SAMPLE_OPPORTUNITIES} />)
        expect(screen.getByText('SaaS business model with recurring revenue')).toBeInTheDocument()
    })

    it('renders the tree component', () => {
        render(<EbitdaSection ebitdaTree={SAMPLE_TREE} opportunities={SAMPLE_OPPORTUNITIES} />)
        expect(screen.getByTestId('ebitda-tree')).toBeInTheDocument()
    })

    it('hides badges when estimates are missing', () => {
        const treeNoEstimates: EbitdaTree = {
            treeData: SAMPLE_TREE.treeData,
        }
        render(<EbitdaSection ebitdaTree={treeNoEstimates} opportunities={[]} />)
        expect(screen.queryByText(/Revenue:/)).toBeNull()
        expect(screen.queryByText(/EBITDA:/)).toBeNull()
    })

    it('hides summary when not provided', () => {
        const treeNoSummary: EbitdaTree = {
            treeData: SAMPLE_TREE.treeData,
            revenueEstimate: '$10M',
        }
        render(<EbitdaSection ebitdaTree={treeNoSummary} opportunities={[]} />)
        expect(screen.queryByText('SaaS business model')).toBeNull()
    })
})
