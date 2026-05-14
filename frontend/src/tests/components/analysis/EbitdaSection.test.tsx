import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'

import type { EbitdaTree, Opportunity } from '@/lib/types/api'

// Mock ``EbitdaTree`` to isolate ``EbitdaSection`` rendering.
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

    it('does NOT render the confidence legend when no node has a confidence level', () => {
        // Older analyses (pre-this-feature) and re-analysed ones whose nodes
        // didn't gain the field should NOT see a legend — there are no chips
        // for the legend to explain.
        render(<EbitdaSection ebitdaTree={SAMPLE_TREE} opportunities={SAMPLE_OPPORTUNITIES} />)
        expect(screen.queryByTestId('ebitda-confidence-legend')).toBeNull()
    })

    it('renders the confidence legend when at least one node carries a level', () => {
        const treeWithConfidence: EbitdaTree = {
            ...SAMPLE_TREE,
            treeData: [
                {
                    id: 'rev',
                    label: 'Revenue',
                    type: 'revenue',
                    value_range: '$10M',
                    parent_id: null,
                    description: 'Total revenue',
                    linked_opportunity_indices: [],
                    confidence_level: 'high',
                    confidence_basis: 'Anchored to template + size.',
                },
            ],
        }
        render(<EbitdaSection ebitdaTree={treeWithConfidence} opportunities={SAMPLE_OPPORTUNITIES} />)
        const legend = screen.getByTestId('ebitda-confidence-legend')
        expect(legend).toBeInTheDocument()
        // Guards against the legend being misread as quality grading
        expect(legend.textContent).toContain('derivation provenance')
        expect(legend.textContent).toContain('not subjective quality')
    })

    it('finds confidence on a deeply-nested child and surfaces the legend', () => {
        const treeNestedConfidence: EbitdaTree = {
            ...SAMPLE_TREE,
            treeData: [
                {
                    id: 'rev',
                    label: 'Revenue',
                    type: 'revenue',
                    value_range: '$10M',
                    parent_id: null,
                    description: 'Total revenue',
                    linked_opportunity_indices: [],
                    children: [
                        {
                            id: 'subs',
                            label: 'Subscriptions',
                            type: 'revenue',
                            value_range: '$8M',
                            parent_id: 'rev',
                            description: 'Sub revenue',
                            linked_opportunity_indices: [],
                            confidence_level: 'medium',
                            confidence_basis: 'Partial signal.',
                        },
                    ],
                },
            ],
        }
        render(<EbitdaSection ebitdaTree={treeNestedConfidence} opportunities={[]} />)
        expect(screen.getByTestId('ebitda-confidence-legend')).toBeInTheDocument()
    })

    // ── Opportunity-link legend (ebitda-opportunity-link-legend) ───────────

    it('renders the opportunity-link legend when at least one leaf carries linked opportunities', () => {
        const treeWithLinks: EbitdaTree = {
            ...SAMPLE_TREE,
            treeData: [
                {
                    id: 'rev',
                    label: 'Revenue',
                    type: 'revenue',
                    value_range: '$10M',
                    parent_id: null,
                    description: 'Total revenue',
                    linked_opportunity_indices: [0],
                },
            ],
        }
        render(<EbitdaSection ebitdaTree={treeWithLinks} opportunities={SAMPLE_OPPORTUNITIES} />)
        const legend = screen.getByTestId('ebitda-opportunity-link-legend')
        expect(legend).toBeInTheDocument()
        // The legend names each of the three lever categories so users
        // can map the chip dots back to the value-lever scale.
        expect(legend.textContent).toContain('Revenue Side')
        expect(legend.textContent).toContain('Cost Side')
        expect(legend.textContent).toContain('Both')
        // And the prose anchor that explains what the dots are FOR.
        expect(legend.textContent).toContain('AI Opportunities targeting this P&L line')
    })

    it('does NOT render the opportunity-link legend when no leaf carries linked opportunities', () => {
        // Older analyses (re-analyse or pre-this-feature) and any tree
        // whose leaves all have empty ``linked_opportunity_indices``
        // arrays should NOT see a legend — there are no chip dots for
        // the legend to explain.
        render(<EbitdaSection ebitdaTree={SAMPLE_TREE} opportunities={SAMPLE_OPPORTUNITIES} />)
        expect(screen.queryByTestId('ebitda-opportunity-link-legend')).toBeNull()
    })

    it('finds linked opportunities on a deeply-nested child and surfaces the legend', () => {
        // The top-level node has no linked opportunities of its own, but
        // a nested child leaf does. The predicate walks recursively.
        const treeNestedLinks: EbitdaTree = {
            ...SAMPLE_TREE,
            treeData: [
                {
                    id: 'rev',
                    label: 'Revenue',
                    type: 'revenue',
                    value_range: '$10M',
                    parent_id: null,
                    description: 'Total revenue',
                    linked_opportunity_indices: [],
                    children: [
                        {
                            id: 'subs',
                            label: 'Subscriptions',
                            type: 'revenue',
                            value_range: '$8M',
                            parent_id: 'rev',
                            description: 'Sub revenue',
                            linked_opportunity_indices: [0],
                        },
                    ],
                },
            ],
        }
        render(<EbitdaSection ebitdaTree={treeNestedLinks} opportunities={SAMPLE_OPPORTUNITIES} />)
        expect(screen.getByTestId('ebitda-opportunity-link-legend')).toBeInTheDocument()
    })

    it('legend dots draw from the same --lever-* theme tokens as the chip dots', () => {
        // Token-binding regression: each of the three legend dots
        // must reference the matching ``var(--lever-*)`` theme token
        // (not a hardcoded hex). Guarantees the legend and chip dots
        // drift together if the palette tokens are ever retuned.
        const treeWithLinks: EbitdaTree = {
            ...SAMPLE_TREE,
            treeData: [
                {
                    id: 'rev',
                    label: 'Revenue',
                    type: 'revenue',
                    value_range: '$10M',
                    parent_id: null,
                    description: 'Total revenue',
                    linked_opportunity_indices: [0],
                },
            ],
        }
        const { container } = render(
            <EbitdaSection ebitdaTree={treeWithLinks} opportunities={SAMPLE_OPPORTUNITIES} />
        )
        const legend = container.querySelector('[data-testid="ebitda-opportunity-link-legend"]')
        expect(legend).not.toBeNull()
        const dotBackgrounds = Array.from(legend!.querySelectorAll<HTMLElement>('span[style]'))
            .map((el) => el.style.background || el.style.backgroundColor)
            .filter((value) => value && value.includes('var(--lever-'))
        // Three dots — one per lever category.
        expect(dotBackgrounds).toHaveLength(3)
        // Each token appears once. Tokens are CSS variables; jsdom
        // surfaces them in the style attribute verbatim.
        expect(dotBackgrounds.some((bg) => bg.includes('--lever-revenue'))).toBe(true)
        expect(dotBackgrounds.some((bg) => bg.includes('--lever-cost'))).toBe(true)
        expect(dotBackgrounds.some((bg) => bg.includes('--lever-both'))).toBe(true)
    })
})
