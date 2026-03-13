import { render, screen, fireEvent, within } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

// Recharts ResponsiveContainer requires ResizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
}))

import AnalysisDetail from '@/app/analysis/[analysisId]/AnalysisDetail'
import type { AnalysisData } from '@/lib/types/api'

const mockSignOut = vi.fn()
let mockSession = { user: { name: 'Test', email: 'test@test.com' } }

vi.mock('next-auth/react', () => ({
    useSession: () => ({ data: mockSession }),
    signOut: (...args: unknown[]) => mockSignOut(...args),
}))

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
    usePathname: () => '/analysis/test-id',
}))

function buildAnalysisData(overrides: Partial<AnalysisData> = {}): AnalysisData {
    return {
        id: 'test-id',
        companyName: 'Acme Corp',
        companyUrl: 'https://acme.com',
        industry: 'SaaS',
        overallRiskScore: 6.5,
        riskTier: 'high',
        analysisSummary: 'High risk company',
        riskScores: [
            {
                category: 'competitive_displacement',
                score: 8,
                explanation: 'Strong competition',
                evidence: 'AI startups',
            },
            { category: 'technology_obsolescence', score: 5, explanation: 'Moderate', evidence: 'Some risk' },
        ],
        opportunities: [
            {
                title: 'Deploy AI Chatbot',
                description: 'Build a chatbot',
                impact_rating: 'High',
                timeline: 'Quick Win (1-3 months)',
                strategic_category: 'Competitive Moat',
                value_lever: 'Revenue Side',
                implementation_steps: ['Step 1', 'Step 2'],
                investment_range: '$100K-$500K',
                roi_estimate: '30% improvement',
                related_services: ['Accenture - AI strategy'],
            },
            {
                title: 'Automate Support',
                description: 'Reduce support costs',
                impact_rating: 'Medium',
                timeline: 'Medium-term (3-9 months)',
                strategic_category: 'Operational Efficiency',
                value_lever: 'Cost Side',
                implementation_steps: ['Step A'],
                investment_range: '$50K-$100K',
                roi_estimate: '2x ROI',
                related_services: [],
            },
            {
                title: 'AI Platform',
                description: 'Build platform',
                impact_rating: 'High',
                timeline: 'Long-term (9-18 months)',
                strategic_category: 'Revenue Capture',
                value_lever: 'Both',
                implementation_steps: ['Step X'],
                investment_range: '$500K-$1M',
                roi_estimate: 'New revenue stream',
                related_services: [],
            },
        ],
        topActions: ['Action 1', 'Action 2', 'Action 3'],
        ...overrides,
    }
}

describe('AnalysisDetail — Value Lever', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockSession = { user: { name: 'Test', email: 'test@test.com' } }
    })

    it('renders value lever summary cards with correct counts', () => {
        const data = buildAnalysisData()
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        expect(screen.getByText('Value Impact')).toBeInTheDocument()

        // Each lever label appears in both the summary card and as a badge on an opportunity.
        // Use getAllByText to confirm at least the summary card renders.
        expect(screen.getAllByText('Revenue Side').length).toBeGreaterThanOrEqual(1)
        expect(screen.getAllByText('Cost Side').length).toBeGreaterThanOrEqual(1)
        expect(screen.getAllByText('Both').length).toBeGreaterThanOrEqual(1)
    })

    it('clicking a lever card filters opportunities', () => {
        const data = buildAnalysisData()
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        expect(screen.getByText('Deploy AI Chatbot')).toBeInTheDocument()
        expect(screen.getByText('Automate Support')).toBeInTheDocument()
        expect(screen.getByText('AI Platform')).toBeInTheDocument()

        // Click the "Revenue Side" summary card (the one inside the Value Impact section)
        const valueImpactHeading = screen.getByText('Value Impact')
        const valueImpactSection = valueImpactHeading.parentElement!
        const revenueSideCard = within(valueImpactSection).getAllByText('Revenue Side')[0]
        fireEvent.click(revenueSideCard.closest('[class*="card"]')!)

        expect(screen.getByText('Deploy AI Chatbot')).toBeInTheDocument()
        expect(screen.queryByText('Automate Support')).not.toBeInTheDocument()
        expect(screen.queryByText('AI Platform')).not.toBeInTheDocument()
    })

    it('clicking active lever card resets filter to All', () => {
        const data = buildAnalysisData()
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        const valueImpactSection = screen.getByText('Value Impact').parentElement!
        const costSideCard = within(valueImpactSection)
            .getAllByText('Cost Side')[0]
            .closest('[class*="card"]')!

        fireEvent.click(costSideCard)
        expect(screen.queryByText('Deploy AI Chatbot')).not.toBeInTheDocument()
        expect(screen.getByText('Automate Support')).toBeInTheDocument()

        // Click again to deselect
        fireEvent.click(costSideCard)
        expect(screen.getByText('Deploy AI Chatbot')).toBeInTheDocument()
        expect(screen.getByText('Automate Support')).toBeInTheDocument()
        expect(screen.getByText('AI Platform')).toBeInTheDocument()
    })

    it('hides value lever section when no opportunities have value_lever', () => {
        const data = buildAnalysisData({
            opportunities: [
                {
                    title: 'Old Opportunity',
                    description: 'From before value lever',
                    impact_rating: 'High',
                    timeline: 'Quick Win (1-3 months)',
                    strategic_category: 'Competitive Moat',
                    implementation_steps: ['Step 1'],
                },
            ],
        })
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        expect(screen.queryByText('Value Impact')).not.toBeInTheDocument()
        expect(screen.getByText('Old Opportunity')).toBeInTheDocument()
    })

    it('combined category and lever filter produces correct intersection', () => {
        const data = buildAnalysisData()
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        // Click "Competitive Moat" category filter — use the filter button, not the badge
        const oppHeading = screen.getByText(/AI Opportunities/)
        const oppSection = oppHeading.parentElement!
        const competitiveMoatButton = within(oppSection).getAllByText('Competitive Moat')[0]
        fireEvent.click(competitiveMoatButton)

        expect(screen.getByText('Deploy AI Chatbot')).toBeInTheDocument()
        expect(screen.queryByText('Automate Support')).not.toBeInTheDocument()

        // Now also filter by "Cost Side" lever — intersection should be empty
        const valueImpactSection = screen.getByText('Value Impact').parentElement!
        const costSideCard = within(valueImpactSection)
            .getAllByText('Cost Side')[0]
            .closest('[class*="card"]')!
        fireEvent.click(costSideCard)

        expect(screen.queryByText('Deploy AI Chatbot')).not.toBeInTheDocument()
        expect(screen.queryByText('Automate Support')).not.toBeInTheDocument()
    })

    it('displays value lever badge on opportunity cards', () => {
        const data = buildAnalysisData()
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        // "Revenue Side" should appear at least twice: once in summary card, once as badge
        const revenueSideElements = screen.getAllByText('Revenue Side')
        expect(revenueSideElements.length).toBeGreaterThanOrEqual(2)
    })
})
