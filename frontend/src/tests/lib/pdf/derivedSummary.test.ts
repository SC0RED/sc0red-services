import { describe, it, expect } from 'vitest'

import { deriveSummary } from '@/lib/pdf/derivedSummary'
import { sortOpportunities } from '@/lib/pdf/sortOpportunities'
import type { AnalysisData, Opportunity, RiskScore } from '@/lib/types/api'

const baseAnalysis: AnalysisData = {
    id: 'a-1',
    companyName: 'Test Co',
    overallRiskScore: 5,
    riskTier: 'moderate',
    riskScores: [],
    opportunities: [],
}

const opp = (overrides: Partial<Opportunity>): Opportunity => ({
    title: 'Untitled',
    description: 'desc',
    impact_rating: 'Low',
    timeline: 'Quick',
    strategic_category: 'Operational Efficiency',
    ...overrides,
})

const rs = (category: string, score: number, rationale?: string): RiskScore => ({
    category,
    score,
    rationale,
})

describe('deriveSummary', () => {
    it('returns null when both riskScores and opportunities are empty', () => {
        const sorted = sortOpportunities([])
        expect(deriveSummary(baseAnalysis, sorted)).toBeNull()
    })

    it('returns a populated summary when only opportunities exist', () => {
        const opportunities = [opp({ title: 'X', impact_rating: 'High' })]
        const result = deriveSummary({ ...baseAnalysis, opportunities }, sortOpportunities(opportunities))
        expect(result).not.toBeNull()
        expect(result!.opportunityHighlights).toHaveLength(1)
        expect(result!.riskDrivers).toHaveLength(0)
    })

    it('returns a populated summary when only riskScores exist', () => {
        const result = deriveSummary(
            { ...baseAnalysis, riskScores: [rs('competitive_displacement', 8, 'Strong threat.')] },
            sortOpportunities([])
        )
        expect(result).not.toBeNull()
        expect(result!.riskDrivers).toHaveLength(1)
        expect(result!.opportunityHighlights).toHaveLength(0)
    })

    it('caps risk drivers at the top 3 by score', () => {
        const riskScores: RiskScore[] = [rs('a', 4), rs('b', 9), rs('c', 7), rs('d', 8), rs('e', 2)]
        const result = deriveSummary({ ...baseAnalysis, riskScores }, sortOpportunities([]))
        expect(result!.riskDrivers.map((r) => r.category)).toEqual(['b', 'd', 'c'])
    })

    it('caps opportunity highlights at the top 3 by impact', () => {
        const opportunities: Opportunity[] = [
            opp({ title: 'L1', impact_rating: 'Low' }),
            opp({ title: 'H1', impact_rating: 'High' }),
            opp({ title: 'M1', impact_rating: 'Medium' }),
            opp({ title: 'H2', impact_rating: 'High' }),
            opp({ title: 'M2', impact_rating: 'Medium' }),
        ]
        const result = deriveSummary({ ...baseAnalysis, opportunities }, sortOpportunities(opportunities))
        expect(result!.opportunityHighlights.map((o) => o.title)).toEqual(['H1', 'H2', 'M1'])
    })

    it('extracts the first sentence of a multi-sentence rationale', () => {
        const result = deriveSummary(
            {
                ...baseAnalysis,
                riskScores: [
                    rs('competitive_displacement', 8, 'Strong threat. Many AI startups already shipping.'),
                ],
            },
            sortOpportunities([])
        )
        expect(result!.riskDrivers[0]?.rationaleFirstSentence).toBe('Strong threat.')
    })

    it('falls back to the full rationale when there is no sentence terminator', () => {
        const result = deriveSummary(
            { ...baseAnalysis, riskScores: [rs('a', 8, 'No terminator here')] },
            sortOpportunities([])
        )
        expect(result!.riskDrivers[0]?.rationaleFirstSentence).toBe('No terminator here')
    })

    it('returns ebitdaUplift when the tree provides at least one of summary/revenue/ebitda', () => {
        const result = deriveSummary(
            {
                ...baseAnalysis,
                riskScores: [rs('a', 8)],
                ebitdaTree: {
                    treeData: [],
                    revenueEstimate: '$10M',
                    ebitdaEstimate: '$2M',
                    businessModelSummary: 'SaaS',
                },
            },
            sortOpportunities([])
        )
        expect(result!.ebitdaUplift).toEqual({
            revenueEstimate: '$10M',
            ebitdaEstimate: '$2M',
            summary: 'SaaS',
        })
    })

    it('returns null ebitdaUplift when the tree is missing', () => {
        const result = deriveSummary({ ...baseAnalysis, riskScores: [rs('a', 8)] }, sortOpportunities([]))
        expect(result!.ebitdaUplift).toBeNull()
    })

    it('returns null ebitdaUplift when tree exists but all summary fields are empty', () => {
        const result = deriveSummary(
            {
                ...baseAnalysis,
                riskScores: [rs('a', 8)],
                ebitdaTree: { treeData: [] },
            },
            sortOpportunities([])
        )
        expect(result!.ebitdaUplift).toBeNull()
    })

    it('aligns opportunityHighlights printedIndex with the sorted array', () => {
        const opportunities: Opportunity[] = [
            opp({ title: 'low', impact_rating: 'Low' }),
            opp({ title: 'high', impact_rating: 'High' }),
        ]
        const sorted = sortOpportunities(opportunities)
        const result = deriveSummary({ ...baseAnalysis, opportunities }, sorted)
        // After sorting, "high" is printedIndex 1.
        expect(result!.opportunityHighlights[0]).toMatchObject({
            title: 'high',
            printedIndex: 1,
        })
    })
})
