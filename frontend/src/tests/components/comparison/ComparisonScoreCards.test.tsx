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

import ComparisonScoreCards from '@/components/comparison/ComparisonScoreCards'
import type { AnalysisData } from '@/lib/types/api'

function buildAnalysis(overrides: Partial<AnalysisData> = {}): AnalysisData {
    return {
        id: 'a-1',
        companyName: 'Acme Corp',
        overallRiskScore: 6.5,
        riskTier: 'high',
        riskScores: [],
        opportunities: [],
        ...overrides,
    }
}

describe('ComparisonScoreCards', () => {
    it('renders a card for each analysis', () => {
        const analyses = [
            buildAnalysis({ id: 'a-1', companyName: 'Acme Corp' }),
            buildAnalysis({ id: 'a-2', companyName: 'Beta Inc' }),
        ]
        render(<ComparisonScoreCards analyses={analyses} />)

        expect(screen.getByText('Acme Corp')).toBeInTheDocument()
        expect(screen.getByText('Beta Inc')).toBeInTheDocument()
    })

    it('renders risk scores', () => {
        const analyses = [
            buildAnalysis({ id: 'a-1', overallRiskScore: 7.2 }),
            buildAnalysis({ id: 'a-2', overallRiskScore: 3.1 }),
        ]
        render(<ComparisonScoreCards analyses={analyses} />)

        expect(screen.getByText('7.2')).toBeInTheDocument()
        expect(screen.getByText('3.1')).toBeInTheDocument()
    })

    it('renders company labels (Company 1, Company 2)', () => {
        const analyses = [buildAnalysis({ id: 'a-1' }), buildAnalysis({ id: 'a-2' })]
        render(<ComparisonScoreCards analyses={analyses} />)

        expect(screen.getByText('Company 1')).toBeInTheDocument()
        expect(screen.getByText('Company 2')).toBeInTheDocument()
    })

    it('renders industry when available', () => {
        const analyses = [buildAnalysis({ id: 'a-1', industry: 'SaaS' }), buildAnalysis({ id: 'a-2' })]
        render(<ComparisonScoreCards analyses={analyses} />)

        expect(screen.getByText('SaaS')).toBeInTheDocument()
    })

    it('supports three analyses', () => {
        const analyses = [
            buildAnalysis({ id: 'a-1', companyName: 'Alpha' }),
            buildAnalysis({ id: 'a-2', companyName: 'Beta' }),
            buildAnalysis({ id: 'a-3', companyName: 'Gamma' }),
        ]
        render(<ComparisonScoreCards analyses={analyses} />)

        expect(screen.getByText('Alpha')).toBeInTheDocument()
        expect(screen.getByText('Beta')).toBeInTheDocument()
        expect(screen.getByText('Gamma')).toBeInTheDocument()
        expect(screen.getByText('Company 3')).toBeInTheDocument()
    })
})
