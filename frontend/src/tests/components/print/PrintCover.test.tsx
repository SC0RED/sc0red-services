import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import PrintCover from '@/components/print/PrintCover'
import type { AnalysisData } from '@/lib/types/api'

const baseAnalysis: AnalysisData = {
    id: 'a-1',
    companyName: 'Acme Corp',
    companyUrl: 'https://acme.test',
    industry: 'SaaS',
    overallRiskScore: 6.2,
    riskTier: 'high',
    analysisSummary: 'A two-sentence thesis line about the company.',
    analyzedAt: '2026-05-19T12:00:00.000Z',
    riskScores: [],
    topActions: [],
    opportunities: [],
}

describe('PrintCover', () => {
    it('renders the sc0red Services wordmark in the eyebrow', () => {
        render(<PrintCover analysis={baseAnalysis} generatedDate="May 19, 2026" />)
        expect(screen.getByText('sc0red Services · AI Risk Report')).toBeInTheDocument()
    })

    it('renders the company name as the cover title', () => {
        render(<PrintCover analysis={baseAnalysis} generatedDate="May 19, 2026" />)
        expect(screen.getByText('Acme Corp')).toBeInTheDocument()
    })

    it('renders the brand footer with generated date and product name', () => {
        render(<PrintCover analysis={baseAnalysis} generatedDate="May 19, 2026" />)
        expect(screen.getByText(/Generated May 19, 2026 · sc0red Services/)).toBeInTheDocument()
    })

    it('renders the overall risk score', () => {
        render(<PrintCover analysis={baseAnalysis} generatedDate="May 19, 2026" />)
        expect(screen.getByText('6.2')).toBeInTheDocument()
    })

    it('renders an em dash when the overall risk score is null', () => {
        render(
            <PrintCover
                analysis={{ ...baseAnalysis, overallRiskScore: null as unknown as number }}
                generatedDate="May 19, 2026"
            />
        )
        expect(screen.getByText('—')).toBeInTheDocument()
    })

    it('omits the company URL line when none is provided', () => {
        render(<PrintCover analysis={{ ...baseAnalysis, companyUrl: '' }} generatedDate="May 19, 2026" />)
        expect(screen.queryByText('https://acme.test')).not.toBeInTheDocument()
    })
})
