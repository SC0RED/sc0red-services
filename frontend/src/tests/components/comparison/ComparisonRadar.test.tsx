import { render, screen } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'

global.ResizeObserver = vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
}))

import ComparisonRadar from '@/components/comparison/ComparisonRadar'
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
        opportunities: [],
        ...overrides,
    }
}

describe('ComparisonRadar', () => {
    it('renders the chart title', () => {
        const analyses = [buildAnalysis({ id: 'a-1' }), buildAnalysis({ id: 'a-2', companyName: 'Beta Inc' })]
        render(<ComparisonRadar analyses={analyses} />)

        expect(screen.getByText('Risk Profile Comparison')).toBeInTheDocument()
    })

    it('renders without crashing for two analyses', () => {
        const analyses = [
            buildAnalysis({ id: 'a-1', companyName: 'Acme Corp' }),
            buildAnalysis({ id: 'a-2', companyName: 'Beta Inc' }),
        ]
        const { container } = render(<ComparisonRadar analyses={analyses} />)

        // Recharts renders an SVG-based chart inside ResponsiveContainer
        expect(container.querySelector('.recharts-responsive-container')).toBeInTheDocument()
    })
})
