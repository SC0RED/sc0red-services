import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

    it('shows opportunity count for linked steps', () => {
        render(
            <ValueChainDiagram steps={SAMPLE_STEPS} opportunities={SAMPLE_OPPORTUNITIES} summary="summary" />
        )
        expect(screen.getByText('1 opportunity')).toBeInTheDocument()
        expect(screen.getByText('2 opportunities')).toBeInTheDocument()
    })

    it('does not show opportunity count for steps with no links', () => {
        render(
            <ValueChainDiagram steps={SAMPLE_STEPS} opportunities={SAMPLE_OPPORTUNITIES} summary="summary" />
        )
        const salesCard = screen.getByText('Sales & Conversion').closest('button')!
        expect(within(salesCard).queryByText(/opportunit/)).toBeNull()
    })

    it('expands step to show linked opportunities on click', async () => {
        const user = userEvent.setup()
        render(
            <ValueChainDiagram steps={SAMPLE_STEPS} opportunities={SAMPLE_OPPORTUNITIES} summary="summary" />
        )
        expect(screen.queryByText('AI Chatbot')).toBeNull()

        const leadGenButton = screen.getByText('Lead Generation & Marketing').closest('button')!
        await user.click(leadGenButton)

        expect(screen.getByText('Linked Opportunities')).toBeInTheDocument()
        expect(screen.getByText('AI Chatbot')).toBeInTheDocument()
    })

    it('collapses expanded step on second click', async () => {
        const user = userEvent.setup()
        render(
            <ValueChainDiagram steps={SAMPLE_STEPS} opportunities={SAMPLE_OPPORTUNITIES} summary="summary" />
        )
        const button = screen.getByText('Lead Generation & Marketing').closest('button')!
        await user.click(button)
        expect(screen.getByText('AI Chatbot')).toBeInTheDocument()

        await user.click(button)
        expect(screen.queryByText('AI Chatbot')).toBeNull()
    })

    it('only one step is expanded at a time', async () => {
        const user = userEvent.setup()
        render(
            <ValueChainDiagram steps={SAMPLE_STEPS} opportunities={SAMPLE_OPPORTUNITIES} summary="summary" />
        )
        const leadGen = screen.getByText('Lead Generation & Marketing').closest('button')!
        const delivery = screen.getByText('Product Delivery & Platform').closest('button')!

        await user.click(leadGen)
        expect(screen.getByText('AI Chatbot')).toBeInTheDocument()

        await user.click(delivery)
        expect(screen.getByText('Process Automation')).toBeInTheDocument()
        // First step's detail should be gone (only one expanded at a time)
        expect(screen.queryByText('Linked Opportunities')).toBeInTheDocument()
    })

    it('hides support section when no support steps exist', () => {
        const primaryOnly = SAMPLE_STEPS.filter((s) => s.category === 'primary')
        render(
            <ValueChainDiagram steps={primaryOnly} opportunities={SAMPLE_OPPORTUNITIES} summary="summary" />
        )
        expect(screen.getByText('Primary Activities')).toBeInTheDocument()
        expect(screen.queryByText('Support Activities')).toBeNull()
    })

    it('handles empty opportunities array gracefully', () => {
        render(<ValueChainDiagram steps={SAMPLE_STEPS} opportunities={[]} summary="summary" />)
        expect(screen.queryByText(/opportunit/)).toBeNull()
    })
})
