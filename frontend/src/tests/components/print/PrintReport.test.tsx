import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import PrintReport from '@/app/print/[analysisId]/PrintReport'
import type { AnalysisData } from '@/lib/types/api'

const fullAnalysis: AnalysisData = {
    id: 'a-1',
    companyName: 'Acme Test Co',
    companyUrl: 'https://acme.test',
    industry: 'B2B SaaS',
    overallRiskScore: 6.5,
    riskTier: 'moderate',
    analysisSummary: 'Two-sentence thesis.',
    riskScores: [
        {
            category: 'competitive_displacement',
            score: 8,
            rationale: 'AI-native entrants are scaling.',
        },
    ],
    opportunities: [
        {
            title: 'Opportunity A',
            description: 'desc A',
            impact_rating: 'High',
            timeline: 'Quick',
            strategic_category: 'Operational Efficiency',
            value_lever: 'Cost Side',
            investment_range: '$50K',
            roi_estimate: '20% reduction',
        },
    ],
    topActions: ['Hire an ML engineer', 'Pilot a chatbot'],
    ebitdaTree: {
        treeData: [
            {
                id: 'root',
                label: 'Operating Revenue',
                type: 'revenue',
                description: '',
                linked_opportunity_indices: [],
                value_range: '$10M',
            },
        ],
        revenueEstimate: '$10M',
        ebitdaEstimate: '$2M',
        businessModelSummary: 'B2B SaaS',
    },
    valueChain: {
        summary: 'Standard chain',
        steps: [
            {
                id: 'p1',
                label: 'Operations',
                description: 'op desc',
                category: 'primary',
                risk_categories: [],
                opportunity_indices: [0],
            },
        ],
    },
}

describe('PrintReport composition', () => {
    it('renders the Executive Summary section', () => {
        render(<PrintReport analysis={fullAnalysis} />)
        expect(screen.getByText('Executive Summary')).toBeInTheDocument()
    })

    it('renders the Methodology section', () => {
        render(<PrintReport analysis={fullAnalysis} />)
        expect(screen.getByText('Methodology')).toBeInTheDocument()
    })

    it('renders exactly one sc0red CTA', () => {
        render(<PrintReport analysis={fullAnalysis} />)
        const matches = screen.getAllByText('sc0red can help you capture these opportunities')
        expect(matches).toHaveLength(1)
    })

    it('omits the back cover when there are no opportunities', () => {
        render(<PrintReport analysis={{ ...fullAnalysis, opportunities: [] }} />)
        expect(screen.queryByText('sc0red can help you capture these opportunities')).not.toBeInTheDocument()
    })

    it('omits the executive summary when both risks and opportunities are empty', () => {
        render(
            <PrintReport
                analysis={{
                    ...fullAnalysis,
                    riskScores: [],
                    opportunities: [],
                    ebitdaTree: undefined,
                    valueChain: undefined,
                }}
            />
        )
        expect(screen.queryByText('Executive Summary')).not.toBeInTheDocument()
    })

    it('renders the Risk Profile, Opportunity Roadmap, EBITDA Impact Model, and Value Chain Analysis sections when data is present', () => {
        render(<PrintReport analysis={fullAnalysis} />)
        expect(screen.getByText('Risk Profile')).toBeInTheDocument()
        expect(screen.getByText('AI Opportunity Roadmap')).toBeInTheDocument()
        expect(screen.getByText('EBITDA Impact Model')).toBeInTheDocument()
        expect(screen.getByText('Value Chain Analysis')).toBeInTheDocument()
    })
})
