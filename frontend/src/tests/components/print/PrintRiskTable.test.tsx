import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import PrintRiskTable from '@/components/print/PrintRiskTable'
import type { RiskScore } from '@/lib/types/api'

const riskScores: RiskScore[] = [
    {
        category: 'competitive_displacement',
        score: 8,
        rationale: 'Strong AI-native entrants in adjacent markets.',
    },
    {
        category: 'talent_workforce',
        score: 3,
        rationale: 'Strong engineering bench, low automation exposure.',
    },
    {
        category: 'margin_compression',
        score: 6,
    },
]

describe('PrintRiskTable', () => {
    it('returns null when riskScores is empty', () => {
        const { container } = render(<PrintRiskTable riskScores={[]} />)
        expect(container.firstChild).toBeNull()
    })

    it('renders rows sorted by score descending', () => {
        const { container } = render(<PrintRiskTable riskScores={riskScores} />)
        const rows = container.querySelectorAll('.print-risk-row')
        expect(rows).toHaveLength(3)
        expect(rows[0].textContent).toContain('Competitive Displacement')
        expect(rows[2].textContent).toContain('Talent & Workforce')
    })

    it('shows the rationale text directly without any expand control', () => {
        render(<PrintRiskTable riskScores={riskScores} />)
        expect(screen.getByText('Strong AI-native entrants in adjacent markets.')).toBeInTheDocument()
        expect(screen.queryByRole('button')).toBeNull()
    })

    it('omits the rationale paragraph for rows with no rationale', () => {
        // Render only the row that has no rationale to make the assertion local.
        const { container } = render(
            <PrintRiskTable riskScores={[{ category: 'margin_compression', score: 6 }]} />
        )
        // Row exists, score visible.
        expect(screen.getByText('Margin Compression')).toBeInTheDocument()
        expect(screen.getByText('6')).toBeInTheDocument()
        // No <p> rendered.
        expect(container.querySelector('p')).toBeNull()
    })

    it('falls back to category id when no display name exists', () => {
        render(<PrintRiskTable riskScores={[{ category: 'unknown_category', score: 4, rationale: 'r' }]} />)
        expect(screen.getByText('unknown_category')).toBeInTheDocument()
    })
})
