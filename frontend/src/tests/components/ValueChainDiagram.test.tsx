import { render, screen, within } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import ValueChainDiagram from '@/components/ValueChainDiagram'
import type { ValueChainStep, Opportunity } from '@/lib/types/api'

const SAMPLE_STEPS: ValueChainStep[] = [
    {
        id: 'lead_generation',
        label: 'Lead Generation & Marketing',
        description: 'Attract and nurture potential customers',
        category: 'primary',
        risk_categories: ['competitive_displacement', 'customer_behavior'],
        opportunity_indices: [0],
    },
    {
        id: 'sales',
        label: 'Sales & Conversion',
        description: 'Convert leads into paying customers',
        category: 'primary',
        risk_categories: ['competitive_displacement', 'margin_compression'],
        opportunity_indices: [],
    },
    {
        id: 'product_delivery',
        label: 'Product Delivery & Platform',
        description: 'Core product functionality',
        category: 'primary',
        risk_categories: ['technology_obsolescence'],
        opportunity_indices: [0, 1],
    },
    {
        id: 'engineering',
        label: 'R&D / Engineering',
        description: 'Product development and innovation',
        category: 'support',
        risk_categories: ['technology_obsolescence', 'talent_workforce'],
        opportunity_indices: [],
    },
]

const SAMPLE_OPPORTUNITIES: Opportunity[] = [
    {
        title: 'AI Chatbot',
        description: 'Implement AI chatbot',
        impact_rating: 'High',
        timeline: '6 months',
        strategic_category: 'Competitive Moat',
        value_lever: 'Revenue Side',
    },
    {
        title: 'Process Automation',
        description: 'Automate ops',
        impact_rating: 'Medium',
        timeline: '3 months',
        strategic_category: 'Operational Efficiency',
        value_lever: 'Cost Side',
    },
]

describe('ValueChainDiagram', () => {
    it('renders the summary without the internal section heading', () => {
        // Per analysis-detail-consistency-wrapper D3, the "Value Chain
        // Analysis" heading is rendered at the page level by
        // `AnalysisSection`. The leaf component renders only the body
        // (summary + activity rows).
        render(
            <ValueChainDiagram
                steps={SAMPLE_STEPS}
                opportunities={SAMPLE_OPPORTUNITIES}
                summary="Test Corp value chain: 3 primary and 1 support"
            />
        )
        expect(screen.queryByText('Value Chain Analysis')).toBeNull()
        expect(screen.getByText(/Test Corp value chain/)).toBeInTheDocument()
    })

    it('renders primary and support activity labels', () => {
        render(
            <ValueChainDiagram steps={SAMPLE_STEPS} opportunities={SAMPLE_OPPORTUNITIES} summary="summary" />
        )
        expect(screen.getByText('Primary Activities')).toBeInTheDocument()
        expect(screen.getByText('Support Activities')).toBeInTheDocument()
    })

    it('renders all step labels', () => {
        render(
            <ValueChainDiagram steps={SAMPLE_STEPS} opportunities={SAMPLE_OPPORTUNITIES} summary="summary" />
        )
        expect(screen.getByText('Lead Generation & Marketing')).toBeInTheDocument()
        expect(screen.getByText('Sales & Conversion')).toBeInTheDocument()
        expect(screen.getByText('Product Delivery & Platform')).toBeInTheDocument()
        expect(screen.getByText('R&D / Engineering')).toBeInTheDocument()
    })

    it('renders step descriptions', () => {
        render(
            <ValueChainDiagram steps={SAMPLE_STEPS} opportunities={SAMPLE_OPPORTUNITIES} summary="summary" />
        )
        expect(screen.getByText('Attract and nurture potential customers')).toBeInTheDocument()
        expect(screen.getByText('Product development and innovation')).toBeInTheDocument()
    })

    it('separates primary and support steps into correct containers', () => {
        render(
            <ValueChainDiagram steps={SAMPLE_STEPS} opportunities={SAMPLE_OPPORTUNITIES} summary="summary" />
        )
        const primaryContainer = screen.getByTestId('primary-activities')
        const supportContainer = screen.getByTestId('support-activities')

        expect(within(primaryContainer).getByText('Lead Generation & Marketing')).toBeInTheDocument()
        expect(within(primaryContainer).getByText('Sales & Conversion')).toBeInTheDocument()
        expect(within(supportContainer).getByText('R&D / Engineering')).toBeInTheDocument()
    })

    it('renders risk category badges on steps', () => {
        render(
            <ValueChainDiagram steps={SAMPLE_STEPS} opportunities={SAMPLE_OPPORTUNITIES} summary="summary" />
        )
        expect(screen.getAllByText('Competitive Displ.')).toHaveLength(2)
        expect(screen.getAllByText('Tech Obsolescence').length).toBeGreaterThanOrEqual(1)
    })

    it('renders the shared opportunity-link dot strip on steps with linked opportunities', () => {
        // P4 of ``redesign-analysis-visuals`` replaced the "X opportunities"
        // count + click-to-expand title list with the shared
        // ``OpportunityDotStrip`` (one coloured dot per linked
        // opportunity, colour from ``LEVER_COLORS``).
        render(
            <ValueChainDiagram steps={SAMPLE_STEPS} opportunities={SAMPLE_OPPORTUNITIES} summary="summary" />
        )
        // Lead Generation step has opportunity_indices: [0] → 1 dot
        const leadGenStrip = screen.getByTestId('value-chain-linked-opportunity-dots-lead_generation')
        expect(leadGenStrip.querySelectorAll('span[aria-hidden="true"]')).toHaveLength(1)
        expect(leadGenStrip).toHaveAttribute('aria-label', '1 opportunity targets this')

        // Product Delivery step has opportunity_indices: [0, 1] → 2 dots
        const deliveryStrip = screen.getByTestId('value-chain-linked-opportunity-dots-product_delivery')
        expect(deliveryStrip.querySelectorAll('span[aria-hidden="true"]')).toHaveLength(2)
        expect(deliveryStrip).toHaveAttribute('aria-label', '2 opportunities target this')
    })

    it('omits the dot strip on steps with no linked opportunities', () => {
        render(
            <ValueChainDiagram steps={SAMPLE_STEPS} opportunities={SAMPLE_OPPORTUNITIES} summary="summary" />
        )
        // Sales step has opportunity_indices: [] → no strip rendered.
        expect(screen.queryByTestId('value-chain-linked-opportunity-dots-sales')).toBeNull()
    })

    it('renders the shared AnalysisLegend when at least one step carries linked opportunities', () => {
        render(
            <ValueChainDiagram steps={SAMPLE_STEPS} opportunities={SAMPLE_OPPORTUNITIES} summary="summary" />
        )
        const legend = screen.getByTestId('value-chain-opportunity-link-legend')
        expect(legend).toBeInTheDocument()
        // Canonical legend copy from the shared ``AnalysisLegend`` —
        // tool-specific noun is "value-chain step".
        expect(legend.textContent).toContain('AI opportunities targeting this value-chain step')
    })

    it('omits the legend when no step carries linked opportunities', () => {
        const stepsWithNoLinks: ValueChainStep[] = SAMPLE_STEPS.map((step) => ({
            ...step,
            opportunity_indices: [],
        }))
        render(
            <ValueChainDiagram
                steps={stepsWithNoLinks}
                opportunities={SAMPLE_OPPORTUNITIES}
                summary="summary"
            />
        )
        expect(screen.queryByTestId('value-chain-opportunity-link-legend')).toBeNull()
    })

    it('does NOT render the legacy expand/collapse button (P4 removed it)', () => {
        // Anti-regression for the click-to-expand interaction. The dot
        // strip's tooltip + the future Phase-5 hover provider replace it.
        render(
            <ValueChainDiagram steps={SAMPLE_STEPS} opportunities={SAMPLE_OPPORTUNITIES} summary="summary" />
        )
        // No buttons inside primary-activities — cards are plain <div>s now.
        const primaryContainer = screen.getByTestId('primary-activities')
        expect(primaryContainer.querySelectorAll('button')).toHaveLength(0)
        // And no "Linked Opportunities" heading anywhere (the expand UI
        // surfaced that label).
        expect(screen.queryByText('Linked Opportunities')).toBeNull()
    })

    it('keeps step cards keyboard-reachable via tabIndex=0', () => {
        // Cards used to be <button> wrappers (the click-to-expand
        // interaction). Now they are <div>s but still need a Tab
        // landing so keyboard users can read each step's content.
        // Mirrors the EBITDA leaf chip's ``<article tabIndex={0}>``
        // pattern.
        render(
            <ValueChainDiagram steps={SAMPLE_STEPS} opportunities={SAMPLE_OPPORTUNITIES} summary="summary" />
        )
        const card = screen.getByTestId('value-chain-step-lead_generation')
        // The inner ``.card`` div is the focusable element.
        const inner = card.querySelector('.card')
        expect(inner?.getAttribute('tabindex')).toBe('0')
    })

    it('hides support section when no support steps exist', () => {
        const primaryOnly = SAMPLE_STEPS.filter((s) => s.category === 'primary')
        render(
            <ValueChainDiagram steps={primaryOnly} opportunities={SAMPLE_OPPORTUNITIES} summary="summary" />
        )
        expect(screen.getByText('Primary Activities')).toBeInTheDocument()
        expect(screen.queryByText('Support Activities')).toBeNull()
    })

    it('handles empty opportunities array gracefully — no strips, no legend', () => {
        // With opportunities=[], every step's linkedIndices resolve to
        // nothing through the strip's out-of-range filter. The legend
        // predicate also requires at least one index that resolves
        // against a real opportunity, so both go away — leaving no
        // orphan "explanation for dots that aren't there".
        render(<ValueChainDiagram steps={SAMPLE_STEPS} opportunities={[]} summary="summary" />)
        expect(screen.queryAllByTestId(/^value-chain-linked-opportunity-dots-/)).toHaveLength(0)
        expect(screen.queryByTestId('value-chain-opportunity-link-legend')).toBeNull()
    })
})
