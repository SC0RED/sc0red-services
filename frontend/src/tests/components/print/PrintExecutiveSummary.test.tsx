import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import PrintExecutiveSummary from '@/components/print/PrintExecutiveSummary'
import type { DerivedSummary } from '@/lib/pdf/derivedSummary'

const fullSummary: DerivedSummary = {
    riskDrivers: [
        {
            category: 'competitive_displacement',
            label: 'Competitive Displacement',
            score: 8,
            rationaleFirstSentence: 'AI competitors are scaling fast.',
        },
        {
            category: 'margin_compression',
            label: 'Margin Compression',
            score: 6,
            rationaleFirstSentence: 'Pricing pressure from automation.',
        },
    ],
    opportunityHighlights: [
        {
            printedIndex: 1,
            title: 'Deploy AI Chatbot',
            impactRating: 'High',
            timeline: 'Quick Win (1-3 months)',
            investmentRange: '$100K-$500K',
        },
    ],
    ebitdaUplift: {
        revenueEstimate: '$10M',
        ebitdaEstimate: '$2M',
        summary: 'B2B SaaS company',
    },
}

describe('PrintExecutiveSummary', () => {
    it('returns null when the upstream summary is null', () => {
        const { container } = render(<PrintExecutiveSummary summary={null} />)
        expect(container.firstChild).toBeNull()
    })

    it('renders all three sub-sections when the summary is fully populated', () => {
        render(<PrintExecutiveSummary summary={fullSummary} />)
        expect(screen.getByText('Executive Summary')).toBeInTheDocument()
        expect(screen.getByText('EBITDA Impact at a Glance')).toBeInTheDocument()
        expect(screen.getByText('Top Opportunities')).toBeInTheDocument()
        expect(screen.getByText('Why this score')).toBeInTheDocument()
    })

    it('renders opportunity highlights with title, investment, timeline, and impact', () => {
        render(<PrintExecutiveSummary summary={fullSummary} />)
        expect(screen.getByText('Deploy AI Chatbot')).toBeInTheDocument()
        // The sibling span shows "— $100K-$500K · Quick Win (1-3 months) · High impact"
        expect(screen.getByText(/\$100K-\$500K · Quick Win \(1-3 months\) · High impact/)).toBeInTheDocument()
    })

    it('renders risk-driver lines with score and label', () => {
        render(<PrintExecutiveSummary summary={fullSummary} />)
        expect(screen.getByText('8')).toBeInTheDocument()
        expect(screen.getByText('Competitive Displacement:')).toBeInTheDocument()
        expect(screen.getByText('AI competitors are scaling fast.')).toBeInTheDocument()
    })

    it('drops the EBITDA block when ebitdaUplift is null', () => {
        const summary: DerivedSummary = { ...fullSummary, ebitdaUplift: null }
        render(<PrintExecutiveSummary summary={summary} />)
        expect(screen.queryByText('EBITDA Impact at a Glance')).not.toBeInTheDocument()
    })

    it('drops the opportunity block when there are no highlights', () => {
        const summary: DerivedSummary = { ...fullSummary, opportunityHighlights: [] }
        render(<PrintExecutiveSummary summary={summary} />)
        expect(screen.queryByText('Top Opportunities')).not.toBeInTheDocument()
    })

    it('drops the risk block when there are no drivers', () => {
        const summary: DerivedSummary = { ...fullSummary, riskDrivers: [] }
        render(<PrintExecutiveSummary summary={summary} />)
        expect(screen.queryByText('Why this score')).not.toBeInTheDocument()
    })

    it('falls back to a default rationale string when first sentence is empty', () => {
        const summary: DerivedSummary = {
            ...fullSummary,
            riskDrivers: [
                {
                    category: 'a',
                    label: 'A',
                    score: 8,
                    rationaleFirstSentence: '',
                },
            ],
            opportunityHighlights: [],
            ebitdaUplift: null,
        }
        render(<PrintExecutiveSummary summary={summary} />)
        expect(screen.getByText('No rationale provided.')).toBeInTheDocument()
    })
})
