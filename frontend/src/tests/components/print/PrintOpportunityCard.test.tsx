import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import PrintOpportunityCard from '@/components/print/PrintOpportunityCard'
import type { Opportunity } from '@/lib/types/api'

const fullOpp: Opportunity = {
    title: 'Deploy AI Chatbot',
    description: 'Build a 24/7 chatbot for customer support.',
    impact_rating: 'High',
    timeline: 'Quick Win (1-3 months)',
    strategic_category: 'Operational Efficiency',
    value_lever: 'Cost Side',
    implementation_steps: ['Step 1: scope', 'Step 2: integrate', 'Step 3: launch'],
    investment_range: '$100K-$500K',
    roi_estimate: '30% cost reduction',
}

describe('PrintOpportunityCard', () => {
    it('renders all populated fields without an expand control', () => {
        render(<PrintOpportunityCard opportunity={fullOpp} printedIndex={3} />)
        expect(screen.getByText('Deploy AI Chatbot')).toBeInTheDocument()
        expect(screen.getByText('Build a 24/7 chatbot for customer support.')).toBeInTheDocument()
        expect(screen.getByText('Step 1: scope')).toBeInTheDocument()
        expect(screen.getByText('Step 2: integrate')).toBeInTheDocument()
        expect(screen.getByText('Step 3: launch')).toBeInTheDocument()
        expect(screen.getByText('$100K-$500K')).toBeInTheDocument()
        expect(screen.getByText('30% cost reduction')).toBeInTheDocument()
        expect(screen.queryByRole('button')).toBeNull()
    })

    it('renders the printedIndex prefix', () => {
        render(<PrintOpportunityCard opportunity={fullOpp} printedIndex={3} />)
        expect(screen.getByText('#3')).toBeInTheDocument()
    })

    it('renders impact, timeline, category, and lever badges', () => {
        render(<PrintOpportunityCard opportunity={fullOpp} printedIndex={1} />)
        expect(screen.getByText('High Impact')).toBeInTheDocument()
        expect(screen.getByText('Quick Win (1-3 months)')).toBeInTheDocument()
        expect(screen.getByText('Operational Efficiency')).toBeInTheDocument()
        expect(screen.getByText('Cost Side')).toBeInTheDocument()
    })

    it('omits implementation steps section when not provided', () => {
        const { container } = render(
            <PrintOpportunityCard
                opportunity={{ ...fullOpp, implementation_steps: undefined }}
                printedIndex={1}
            />
        )
        expect(screen.queryByText('Implementation Steps')).not.toBeInTheDocument()
        expect(container.querySelector('ol')).toBeNull()
    })

    it('omits investment / ROI grid when both fields are empty', () => {
        render(
            <PrintOpportunityCard
                opportunity={{ ...fullOpp, investment_range: undefined, roi_estimate: undefined }}
                printedIndex={1}
            />
        )
        expect(screen.queryByText('Estimated Investment')).not.toBeInTheDocument()
        expect(screen.queryByText('Potential ROI')).not.toBeInTheDocument()
    })

    it('renders only investment when ROI is missing', () => {
        render(
            <PrintOpportunityCard opportunity={{ ...fullOpp, roi_estimate: undefined }} printedIndex={1} />
        )
        expect(screen.getByText('Estimated Investment')).toBeInTheDocument()
        expect(screen.queryByText('Potential ROI')).not.toBeInTheDocument()
    })

    it('omits the lever badge when no value_lever is set', () => {
        render(<PrintOpportunityCard opportunity={{ ...fullOpp, value_lever: undefined }} printedIndex={1} />)
        expect(screen.queryByText('Cost Side')).not.toBeInTheDocument()
    })
})
