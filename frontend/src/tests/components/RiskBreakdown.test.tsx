import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import RiskBreakdown from '@/components/RiskBreakdown'
import type { RiskScore } from '@/lib/types/api'

const mockRiskScores: RiskScore[] = [
    {
        category: 'competitive_displacement',
        score: 8,
        rationale: 'Strong competition from AI startups',
    },
    {
        category: 'technology_obsolescence',
        score: 5,
        rationale: 'Moderate risk from some legacy systems',
    },
    {
        category: 'talent_workforce',
        score: 3,
        rationale: 'Low talent risk due to strong team',
    },
]

describe('RiskBreakdown', () => {
    it('renders all risk scores sorted by score descending', () => {
        render(<RiskBreakdown riskScores={mockRiskScores} />)

        const buttons = screen.getAllByRole('button')
        const scores = buttons.map((button) => button.textContent)

        // First item should contain score 8 (highest), last should contain score 3 (lowest)
        expect(scores[0]).toContain('8')
        expect(scores[2]).toContain('3')
    })

    it('shows category name and score for each risk', () => {
        render(<RiskBreakdown riskScores={mockRiskScores} />)

        expect(screen.getByText('Competitive Displacement')).toBeInTheDocument()
        expect(screen.getByText('Technology Obsolescence')).toBeInTheDocument()
        expect(screen.getByText('Talent & Workforce')).toBeInTheDocument()
        expect(screen.getByText('8')).toBeInTheDocument()
        expect(screen.getByText('5')).toBeInTheDocument()
        expect(screen.getByText('3')).toBeInTheDocument()
    })

    it('clicking a risk item expands it and shows rationale', () => {
        render(<RiskBreakdown riskScores={mockRiskScores} />)

        expect(screen.queryByText('Strong competition from AI startups')).not.toBeInTheDocument()

        const competitiveButton = screen.getByText('Competitive Displacement').closest('button')!
        fireEvent.click(competitiveButton)

        expect(screen.getByText('Strong competition from AI startups')).toBeInTheDocument()
        expect(competitiveButton).toHaveAttribute('aria-expanded', 'true')
    })

    it('clicking an expanded risk item collapses it', () => {
        render(<RiskBreakdown riskScores={mockRiskScores} />)

        const competitiveButton = screen.getByText('Competitive Displacement').closest('button')!

        // Expand
        fireEvent.click(competitiveButton)
        expect(screen.getByText('Strong competition from AI startups')).toBeInTheDocument()

        // Collapse
        fireEvent.click(competitiveButton)
        expect(screen.queryByText('Strong competition from AI startups')).not.toBeInTheDocument()
        expect(competitiveButton).toHaveAttribute('aria-expanded', 'false')
    })

    it('shows RiskBadge with correct tier for each score', () => {
        render(<RiskBreakdown riskScores={mockRiskScores} />)

        // score 8 -> high tier -> "High Risk"
        expect(screen.getByText('High Risk')).toBeInTheDocument()
        // score 5 -> moderate tier -> "Moderate Risk"
        expect(screen.getByText('Moderate Risk')).toBeInTheDocument()
        // score 3 -> low tier -> "Low Risk"
        expect(screen.getByText('Low Risk')).toBeInTheDocument()
    })

    it('does NOT render an internal section heading (page-level wrapper owns the title)', () => {
        // Per analysis-detail-consistency-wrapper D3, the "Risk Breakdown"
        // heading is rendered at the page level by `AnalysisSection`.
        // The leaf component must not render it again — duplicating the
        // heading was the failure mode that necessitated the wrapper.
        render(<RiskBreakdown riskScores={mockRiskScores} />)
        expect(screen.queryByText('Risk Breakdown')).toBeNull()
    })

    it('falls back to category id when name is not found', () => {
        const scores: RiskScore[] = [{ category: 'unknown_category', score: 7, rationale: 'Unknown' }]
        render(<RiskBreakdown riskScores={scores} />)
        expect(screen.getByText('unknown_category')).toBeInTheDocument()
    })
})
