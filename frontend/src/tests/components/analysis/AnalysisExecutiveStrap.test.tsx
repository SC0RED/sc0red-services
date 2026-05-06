import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import AnalysisExecutiveStrap from '@/components/analysis/AnalysisExecutiveStrap'
import type { AnalysisData } from '@/lib/types/api'

/**
 * Coverage focus: the strap is a marketing-grade one-line summary, so
 * what matters is (a) every required segment renders, (b) every
 * conditional segment drops cleanly when its source data is absent
 * (no orphaned separators, no placeholder strings), and (c) the score
 * formats to one decimal regardless of input precision.
 *
 * We assert via composed text matching (`screen.getByText`) so the test
 * stays robust against trivial markup changes within the strap.
 */

function buildData(overrides: Partial<AnalysisData> = {}): AnalysisData {
    return {
        id: 'a-1',
        companyName: 'Acme Corp',
        overallRiskScore: 5.8,
        riskTier: 'moderate',
        riskScores: [],
        opportunities: [],
        ...overrides,
    }
}

describe('AnalysisExecutiveStrap', () => {
    it('renders all five segments when full data is available', () => {
        const data = buildData({
            opportunities: [
                {
                    title: 'Op 1',
                    description: 'd',
                    impact_rating: 'High',
                    timeline: 'Quick Win',
                    strategic_category: 'X',
                },
                {
                    title: 'Op 2',
                    description: 'd',
                    impact_rating: 'High',
                    timeline: 'Quick Win',
                    strategic_category: 'X',
                },
                {
                    title: 'Op 3',
                    description: 'd',
                    impact_rating: 'High',
                    timeline: 'Quick Win',
                    strategic_category: 'X',
                },
                {
                    title: 'Op 4',
                    description: 'd',
                    impact_rating: 'High',
                    timeline: 'Quick Win',
                    strategic_category: 'X',
                },
                {
                    title: 'Op 5',
                    description: 'd',
                    impact_rating: 'High',
                    timeline: 'Quick Win',
                    strategic_category: 'X',
                },
            ],
            ebitdaTree: {
                treeData: [],
                ebitdaEstimate: '$5M-$140M',
            },
            analyzedAt: '2026-05-05T10:00:00Z',
        })
        render(<AnalysisExecutiveStrap data={data} />)
        expect(screen.getByText('Acme Corp')).toBeInTheDocument()
        expect(screen.getByText('5.8')).toBeInTheDocument() // toFixed(1) on 5.8 = "5.8"
        expect(screen.getByText('Moderate')).toBeInTheDocument()
        expect(screen.getByText('5 opportunities')).toBeInTheDocument()
        expect(screen.getByText(/est\. EBITDA range \$5M-\$140M/)).toBeInTheDocument()
        expect(screen.getByText(/last analysed/)).toBeInTheDocument()
        // Date format check: "May 5, 2026" via UTC-deterministic
        // formatAbsoluteUTC (matches RelativeTime's SSR-safe pattern).
        expect(screen.getByText(/May 5, 2026/)).toBeInTheDocument()
    })

    it('omits the EBITDA segment when ebitdaTree is missing', () => {
        const data = buildData({ analyzedAt: '2026-05-05T10:00:00Z' })
        // No ebitdaTree.
        render(<AnalysisExecutiveStrap data={data} />)
        expect(screen.queryByText(/EBITDA range/)).toBeNull()
        // But the rest still renders.
        expect(screen.getByText(/last analysed/)).toBeInTheDocument()
    })

    it('omits the EBITDA segment when ebitdaTree exists but ebitdaEstimate is undefined', () => {
        const data = buildData({
            ebitdaTree: { treeData: [] }, // tree exists but no precomputed estimate
            analyzedAt: '2026-05-05T10:00:00Z',
        })
        render(<AnalysisExecutiveStrap data={data} />)
        expect(screen.queryByText(/EBITDA range/)).toBeNull()
    })

    it('omits the last-analysed segment when analyzedAt is missing', () => {
        const data = buildData({
            ebitdaTree: { treeData: [], ebitdaEstimate: '$1M-$2M' },
        })
        render(<AnalysisExecutiveStrap data={data} />)
        expect(screen.queryByText(/last analysed/)).toBeNull()
        expect(screen.getByText(/EBITDA range \$1M-\$2M/)).toBeInTheDocument()
    })

    it('shows zero opportunities when the array is empty', () => {
        const data = buildData()
        render(<AnalysisExecutiveStrap data={data} />)
        expect(screen.getByText('0 opportunities')).toBeInTheDocument()
    })

    it('formats the score to one decimal place', () => {
        const data = buildData({ overallRiskScore: 7 })
        render(<AnalysisExecutiveStrap data={data} />)
        expect(screen.getByText('7.0')).toBeInTheDocument()
    })

    it('derives the tier from the score when riskTier is null', () => {
        // 7.5 falls in the "high" band per getRiskTier (>6, ≤8).
        const data = buildData({ overallRiskScore: 7.5, riskTier: null })
        render(<AnalysisExecutiveStrap data={data} />)
        expect(screen.getByText('High')).toBeInTheDocument()
    })

    it('renders an em-dash for both score and tier when both are null', () => {
        const data = buildData({ overallRiskScore: null, riskTier: null })
        render(<AnalysisExecutiveStrap data={data} />)
        // Both placeholder strongs render "—"
        const placeholders = screen.getAllByText('—')
        expect(placeholders.length).toBeGreaterThanOrEqual(2)
    })

    it('falls back to em-dash placeholders when score is undefined (contract drift defence)', () => {
        // The API contract types `overallRiskScore` as `number | null`,
        // but the component guards with `typeof === 'number'` so a
        // future schema relaxation introducing `undefined` doesn't
        // crash the strap with `undefined.toFixed(1)`.
        const data = buildData()
        // Force the field to undefined to simulate a drifted API.
        const drifted = {
            ...data,
            overallRiskScore: undefined as unknown as number | null,
            riskTier: null,
        }
        render(<AnalysisExecutiveStrap data={drifted} />)
        expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2)
    })

    it('falls back to em-dash placeholders when score is NaN', () => {
        // Same defensive principle: `NaN.toFixed(1)` returns "NaN" as
        // a string, which would render in the strap. The
        // `Number.isFinite` guard catches this.
        const data = buildData({ overallRiskScore: Number.NaN, riskTier: null })
        render(<AnalysisExecutiveStrap data={data} />)
        expect(screen.queryByText(/NaN/)).toBeNull()
        expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2)
    })

    it('exposes a stable testid for the strap root', () => {
        const data = buildData()
        render(<AnalysisExecutiveStrap data={data} />)
        expect(screen.getByTestId('analysis-executive-strap')).toBeInTheDocument()
    })
})
