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
        render(<PrintReport analysis={fullAnalysis} generatedDate="May 1, 2026" />)
        expect(screen.getByText('Executive Summary')).toBeInTheDocument()
    })

    it('renders the Methodology section', () => {
        render(<PrintReport analysis={fullAnalysis} generatedDate="May 1, 2026" />)
        expect(screen.getByText('Methodology')).toBeInTheDocument()
    })

    it('renders exactly one sc0red CTA', () => {
        render(<PrintReport analysis={fullAnalysis} generatedDate="May 1, 2026" />)
        const matches = screen.getAllByText('sc0red Advisory can help you capture these opportunities')
        expect(matches).toHaveLength(1)
    })

    it('omits the back cover when there are no opportunities', () => {
        render(<PrintReport analysis={{ ...fullAnalysis, opportunities: [] }} generatedDate="May 1, 2026" />)
        expect(
            screen.queryByText('sc0red Advisory can help you capture these opportunities')
        ).not.toBeInTheDocument()
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
                generatedDate="May 1, 2026"
            />
        )
        expect(screen.queryByText('Executive Summary')).not.toBeInTheDocument()
    })

    it('renders coherently for a fully-empty analysis (no risks, opps, top actions, ebitda, or value chain)', () => {
        // Sparse analyses must not produce broken layouts or empty
        // sections. Cover and Methodology Appendix should still render;
        // every other section component returns null and the back cover
        // is omitted.
        render(
            <PrintReport
                analysis={{
                    ...fullAnalysis,
                    riskScores: [],
                    opportunities: [],
                    topActions: [],
                    ebitdaTree: undefined,
                    valueChain: undefined,
                }}
                generatedDate="May 1, 2026"
            />
        )
        // Company name appears twice: cover h1 + Methodology Subject block.
        expect(screen.getAllByText('Acme Test Co').length).toBeGreaterThanOrEqual(1)
        expect(screen.getByText('Methodology')).toBeInTheDocument()
        expect(screen.queryByText('Executive Summary')).not.toBeInTheDocument()
        expect(screen.queryByText('Risk Profile')).not.toBeInTheDocument()
        expect(screen.queryByText('AI Opportunity Roadmap')).not.toBeInTheDocument()
        expect(screen.queryByText('EBITDA Impact Model')).not.toBeInTheDocument()
        expect(screen.queryByText('Value Chain Analysis')).not.toBeInTheDocument()
        expect(
            screen.queryByText('sc0red Advisory can help you capture these opportunities')
        ).not.toBeInTheDocument()
    })

    it('renders the Risk Profile, Opportunity Roadmap, EBITDA Impact Model, and Value Chain Analysis sections when data is present', () => {
        render(<PrintReport analysis={fullAnalysis} generatedDate="May 1, 2026" />)
        expect(screen.getByText('Risk Profile')).toBeInTheDocument()
        expect(screen.getByText('AI Opportunity Roadmap')).toBeInTheDocument()
        expect(screen.getByText('EBITDA Impact Model')).toBeInTheDocument()
        expect(screen.getByText('Value Chain Analysis')).toBeInTheDocument()
    })

    it('omits the Strategy Map section when analysis.strategyMap is missing', () => {
        // Default fixture has no strategyMap — confirms legacy analyses
        // render the rest of the PDF cleanly without the new section.
        render(<PrintReport analysis={fullAnalysis} generatedDate="May 1, 2026" />)
        expect(screen.queryByText('Strategy Map')).not.toBeInTheDocument()
    })

    it('renders the Strategy Map section when analysis.strategyMap is populated', () => {
        const strategyMap: AnalysisData['strategyMap'] = {
            vision: { statement: 'V', synthesised: false, rationale: 'r' },
            mission: { statement: 'M', synthesised: false, rationale: 'r' },
            valueProposition: {
                primary: 'customer_intimacy',
                secondary: null,
                rationale: 'Public materials emphasise associate friendliness.',
            },
            strategicPriorities: [
                { name: 'Grow Through X', result: 'best-in-class X' },
                { name: 'Deliver Y', result: 'industry-leading Y perception' },
            ],
            financial: {
                objectives: [
                    {
                        id: 'F1',
                        title: 'Grow revenue',
                        definition:
                            'We will grow revenue across markets through deepened engagement and adjacent expansion driving year-over-year growth.',
                        category: 'revenue_growth',
                        confidence: 'HIGH',
                    },
                ] as never, // truncated for brevity; full schema isn't required for this assertion
            } as never,
            customer: { objectives: [] as never } as never,
            internalProcesses: { themes: [] as never } as never,
            organizationalCapacity: {
                people: {
                    id: 'O.P',
                    title: 'p',
                    definition: 'pdef pdef pdef pdef pdef pdef pdef pdef pdef pdef pdef pdef',
                    confidence: 'MEDIUM',
                },
                technology: {
                    id: 'O.T',
                    title: 't',
                    definition: 'tdef tdef tdef tdef tdef tdef tdef tdef tdef tdef tdef tdef',
                    confidence: 'MEDIUM',
                },
                culture: {
                    id: 'O.C',
                    title: 'c',
                    definition: 'cdef cdef cdef cdef cdef cdef cdef cdef cdef cdef cdef cdef',
                    confidence: 'LOW',
                },
            },
            arrows: [],
            coreValues: { values: ['a', 'b', 'c'], synthesised: true, rationale: 'r' },
        }
        render(<PrintReport analysis={{ ...fullAnalysis, strategyMap }} generatedDate="May 1, 2026" />)
        expect(screen.getByText('Strategy Map')).toBeInTheDocument()
        // The "Strategic gaps to address" print-only section was removed
        // by the ``redesign-strategy-map`` Phase 2 change.
        expect(screen.queryByText('Strategic gaps to address')).not.toBeInTheDocument()
    })
})
