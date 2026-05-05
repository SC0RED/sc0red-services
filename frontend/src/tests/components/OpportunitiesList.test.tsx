import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import OpportunitiesList from '@/components/OpportunitiesList'
import type { Opportunity } from '@/lib/types/api'

const mockOpportunities: Opportunity[] = [
    {
        title: 'Deploy AI Chatbot',
        description: 'Build a chatbot for customer support',
        impact_rating: 'High',
        timeline: 'Quick Win (1-3 months)',
        strategic_category: 'Competitive Moat',
        value_lever: 'Revenue Side',
        implementation_steps: ['Step 1', 'Step 2'],
        investment_range: '$100K-$500K',
        roi_estimate: '30% improvement',
    },
    {
        title: 'Automate Support',
        description: 'Reduce support costs with automation',
        impact_rating: 'Medium',
        timeline: 'Medium-term (3-9 months)',
        strategic_category: 'Operational Efficiency',
        value_lever: 'Cost Side',
        implementation_steps: ['Step A'],
        investment_range: '$50K-$100K',
        roi_estimate: '2x ROI',
    },
    {
        title: 'AI Platform',
        description: 'Build a platform for AI services',
        impact_rating: 'High',
        timeline: 'Long-term (9-18 months)',
        strategic_category: 'Competitive Moat',
        value_lever: 'Both',
        implementation_steps: ['Step X'],
        investment_range: '$500K-$1M',
        roi_estimate: 'New revenue stream',
    },
]

describe('OpportunitiesList', () => {
    it('renders all opportunities with titles', () => {
        render(<OpportunitiesList opportunities={mockOpportunities} activeLever="All" />)

        expect(screen.getByText('Deploy AI Chatbot')).toBeInTheDocument()
        expect(screen.getByText('Automate Support')).toBeInTheDocument()
        expect(screen.getByText('AI Platform')).toBeInTheDocument()
    })

    it('shows category filter buttons', () => {
        render(<OpportunitiesList opportunities={mockOpportunities} activeLever="All" />)

        expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Competitive Moat' })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Operational Efficiency' })).toBeInTheDocument()
    })

    it('clicking a category filter shows only matching opportunities', () => {
        render(<OpportunitiesList opportunities={mockOpportunities} activeLever="All" />)

        fireEvent.click(screen.getByRole('button', { name: 'Operational Efficiency' }))

        expect(screen.getByText('Automate Support')).toBeInTheDocument()
        expect(screen.queryByText('Deploy AI Chatbot')).not.toBeInTheDocument()
        expect(screen.queryByText('AI Platform')).not.toBeInTheDocument()
    })

    it('clicking "All" shows all opportunities', () => {
        render(<OpportunitiesList opportunities={mockOpportunities} activeLever="All" />)

        // Filter first
        fireEvent.click(screen.getByRole('button', { name: 'Operational Efficiency' }))
        expect(screen.queryByText('Deploy AI Chatbot')).not.toBeInTheDocument()

        // Reset
        fireEvent.click(screen.getByRole('button', { name: 'All' }))
        expect(screen.getByText('Deploy AI Chatbot')).toBeInTheDocument()
        expect(screen.getByText('Automate Support')).toBeInTheDocument()
        expect(screen.getByText('AI Platform')).toBeInTheDocument()
    })

    it('clicking an opportunity expands details', () => {
        render(<OpportunitiesList opportunities={mockOpportunities} activeLever="All" />)

        expect(screen.queryByText('Build a chatbot for customer support')).not.toBeInTheDocument()

        const chatbotButton = screen.getByText('Deploy AI Chatbot').closest('button')!
        fireEvent.click(chatbotButton)

        expect(screen.getByText('Build a chatbot for customer support')).toBeInTheDocument()
        expect(screen.getByText('Implementation Steps')).toBeInTheDocument()
        expect(screen.getByText('Step 1')).toBeInTheDocument()
        expect(screen.getByText('Step 2')).toBeInTheDocument()
        expect(screen.getByText('$100K-$500K')).toBeInTheDocument()
        expect(screen.getByText('30% improvement')).toBeInTheDocument()
    })

    it('does not render the sc0red CTA banner — that lives at the parent surface now', () => {
        // CTA was lifted to AnalysisDetail in improve-pdf-export-content
        // so screen + print PDF have a single source of truth.
        render(<OpportunitiesList opportunities={mockOpportunities} activeLever="All" />)

        expect(screen.queryByText('sc0red can help you capture these opportunities')).not.toBeInTheDocument()
    })

    it('shows ImpactBadge and TimelineBadge for each opportunity', () => {
        render(<OpportunitiesList opportunities={mockOpportunities} activeLever="All" />)

        // Two opportunities have "High" impact
        expect(screen.getAllByText('High Impact').length).toBe(2)
        expect(screen.getByText('Medium Impact')).toBeInTheDocument()
        expect(screen.getByText('Quick Win (1-3 months)')).toBeInTheDocument()
        expect(screen.getByText('Medium-term (3-9 months)')).toBeInTheDocument()
    })

    it('activeLever filter works', () => {
        render(<OpportunitiesList opportunities={mockOpportunities} activeLever="Cost Side" />)

        expect(screen.getByText('Automate Support')).toBeInTheDocument()
        expect(screen.queryByText('Deploy AI Chatbot')).not.toBeInTheDocument()
        expect(screen.queryByText('AI Platform')).not.toBeInTheDocument()
    })

    it('does NOT render an internal "AI Opportunities" heading (page-level wrapper owns it)', () => {
        // Per analysis-detail-consistency-wrapper D3, the heading +
        // count badge `AI Opportunities ({n})` is rendered at the
        // page level by `AnalysisSection`. The leaf renders only
        // the category-chip filter row and the opportunity cards.
        render(<OpportunitiesList opportunities={mockOpportunities} activeLever="All" />)
        expect(screen.queryByText(/AI Opportunities/)).toBeNull()
    })

    it('combined category and lever filter produces intersection', () => {
        render(<OpportunitiesList opportunities={mockOpportunities} activeLever="Revenue Side" />)

        // activeLever=Revenue Side filters to only Deploy AI Chatbot and the Competitive Moat category
        fireEvent.click(screen.getByRole('button', { name: 'Competitive Moat' }))

        expect(screen.getByText('Deploy AI Chatbot')).toBeInTheDocument()
        expect(screen.queryByText('AI Platform')).not.toBeInTheDocument()
    })
})
