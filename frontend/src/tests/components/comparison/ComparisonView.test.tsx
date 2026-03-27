import { render, screen } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'

global.ResizeObserver = vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
}))

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn() }),
    usePathname: () => '/analyses/compare',
}))

vi.mock('next-auth/react', () => ({
    useSession: () => ({ data: { user: { name: 'Test' } } }),
    signOut: vi.fn(),
}))

vi.mock('@/components/DashboardSidebar', () => ({
    default: () => <div data-testid="dashboard-sidebar">Sidebar</div>,
}))

import ComparisonView from '@/components/comparison/ComparisonView'
import type { AnalysisData } from '@/lib/types/api'

function buildAnalysis(overrides: Partial<AnalysisData> = {}): AnalysisData {
    return {
        id: 'a-1',
        companyName: 'Acme Corp',
        overallRiskScore: 6.5,
        riskTier: 'high',
        riskScores: [
            { category: 'competitive_displacement', score: 8 },
            { category: 'technology_obsolescence', score: 5 },
        ],
        opportunities: [
            {
                title: 'Deploy AI',
                description: 'Build AI',
                impact_rating: 'High',
                timeline: 'Quick Win',
                strategic_category: 'Competitive Moat',
                value_lever: 'Revenue Side',
            },
        ],
        ...overrides,
    }
}

describe('ComparisonView', () => {
    it('renders the comparison heading', () => {
        const analyses = [buildAnalysis({ id: 'a-1' }), buildAnalysis({ id: 'a-2', companyName: 'Beta Inc' })]
        render(<ComparisonView analyses={analyses} />)

        expect(screen.getByText('Comparing 2 Companies')).toBeInTheDocument()
    })

    it('renders back link to analyses', () => {
        const analyses = [buildAnalysis({ id: 'a-1' }), buildAnalysis({ id: 'a-2', companyName: 'Beta Inc' })]
        render(<ComparisonView analyses={analyses} />)

        expect(screen.getByText('All Analyses')).toBeInTheDocument()
    })

    it('renders company names in score cards', () => {
        const analyses = [
            buildAnalysis({ id: 'a-1', companyName: 'Acme Corp' }),
            buildAnalysis({ id: 'a-2', companyName: 'Beta Inc' }),
        ]
        render(<ComparisonView analyses={analyses} />)

        expect(screen.getAllByText('Acme Corp').length).toBeGreaterThanOrEqual(1)
        expect(screen.getAllByText('Beta Inc').length).toBeGreaterThanOrEqual(1)
    })

    it('renders opportunity overview section', () => {
        const analyses = [
            buildAnalysis({
                id: 'a-1',
                companyName: 'Acme',
                opportunities: [
                    {
                        title: 'Op1',
                        description: '',
                        impact_rating: 'High',
                        timeline: '',
                        strategic_category: '',
                    },
                    {
                        title: 'Op2',
                        description: '',
                        impact_rating: 'Medium',
                        timeline: '',
                        strategic_category: '',
                    },
                ],
            }),
            buildAnalysis({
                id: 'a-2',
                companyName: 'Beta',
                opportunities: [
                    {
                        title: 'Op3',
                        description: '',
                        impact_rating: 'Low',
                        timeline: '',
                        strategic_category: '',
                    },
                ],
            }),
        ]
        render(<ComparisonView analyses={analyses} />)

        expect(screen.getByText('Opportunities Overview')).toBeInTheDocument()
        // Acme: 1 High, 1 Medium
        expect(screen.getByText('1 High · 1 Medium · 0 Low')).toBeInTheDocument()
        // Beta: 1 Low
        expect(screen.getByText('0 High · 0 Medium · 1 Low')).toBeInTheDocument()
    })

    it('renders for three companies', () => {
        const analyses = [
            buildAnalysis({ id: 'a-1', companyName: 'Alpha' }),
            buildAnalysis({ id: 'a-2', companyName: 'Beta' }),
            buildAnalysis({ id: 'a-3', companyName: 'Gamma' }),
        ]
        render(<ComparisonView analyses={analyses} />)

        expect(screen.getByText('Comparing 3 Companies')).toBeInTheDocument()
    })
})
