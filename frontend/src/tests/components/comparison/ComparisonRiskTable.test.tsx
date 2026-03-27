import { render, screen } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn() }),
    usePathname: () => '/analyses/compare',
}))

vi.mock('next-auth/react', () => ({
    useSession: () => ({ data: { user: { name: 'Test' } } }),
    signOut: vi.fn(),
}))

import ComparisonRiskTable from '@/components/comparison/ComparisonRiskTable'
import type { AnalysisData } from '@/lib/types/api'

function buildAnalysis(overrides: Partial<AnalysisData> = {}): AnalysisData {
    return {
        id: 'a-1',
        companyName: 'Acme Corp',
        overallRiskScore: 6.5,
        riskTier: 'high',
        riskScores: [
            { category: 'competitive_displacement', score: 8 },
            { category: 'technology_obsolescence', score: 3 },
        ],
        opportunities: [],
        ...overrides,
    }
}

describe('ComparisonRiskTable', () => {
    it('renders the table title', () => {
        const analyses = [buildAnalysis({ id: 'a-1' }), buildAnalysis({ id: 'a-2', companyName: 'Beta Inc' })]
        render(<ComparisonRiskTable analyses={analyses} />)

        expect(screen.getByText('Risk Dimension Breakdown')).toBeInTheDocument()
    })

    it('renders company names as column headers', () => {
        const analyses = [
            buildAnalysis({ id: 'a-1', companyName: 'Acme Corp' }),
            buildAnalysis({ id: 'a-2', companyName: 'Beta Inc' }),
        ]
        render(<ComparisonRiskTable analyses={analyses} />)

        expect(screen.getByText('Acme Corp')).toBeInTheDocument()
        expect(screen.getByText('Beta Inc')).toBeInTheDocument()
    })

    it('renders risk category labels', () => {
        const analyses = [buildAnalysis({ id: 'a-1' }), buildAnalysis({ id: 'a-2', companyName: 'Beta Inc' })]
        render(<ComparisonRiskTable analyses={analyses} />)

        expect(screen.getByText('Competitive Displ.')).toBeInTheDocument()
        expect(screen.getByText('Tech Obsolescence')).toBeInTheDocument()
    })

    it('renders scores for each company', () => {
        const analyses = [
            buildAnalysis({
                id: 'a-1',
                riskScores: [{ category: 'competitive_displacement', score: 8.5 }],
            }),
            buildAnalysis({
                id: 'a-2',
                companyName: 'Beta Inc',
                riskScores: [{ category: 'competitive_displacement', score: 3.2 }],
            }),
        ]
        render(<ComparisonRiskTable analyses={analyses} />)

        expect(screen.getByText('8.5')).toBeInTheDocument()
        expect(screen.getByText('3.2')).toBeInTheDocument()
    })

    it('shows 0.0 for missing risk scores', () => {
        const analyses = [
            buildAnalysis({ id: 'a-1', riskScores: [] }),
            buildAnalysis({ id: 'a-2', companyName: 'Beta Inc', riskScores: [] }),
        ]
        render(<ComparisonRiskTable analyses={analyses} />)

        const zeroes = screen.getAllByText('0.0')
        expect(zeroes.length).toBeGreaterThanOrEqual(2)
    })
})
