import { describe, it, expect } from 'vitest'

import { findByOriginalIndex, sortOpportunities } from '@/lib/pdf/sortOpportunities'
import type { Opportunity } from '@/lib/types/api'

const make = (overrides: Partial<Opportunity>): Opportunity => ({
    title: 'Untitled',
    description: 'desc',
    impact_rating: 'Low',
    timeline: 'Quick',
    strategic_category: 'Operational Efficiency',
    ...overrides,
})

describe('sortOpportunities', () => {
    it('returns an empty array for empty input', () => {
        expect(sortOpportunities([])).toEqual([])
    })

    it('returns a single entry with printedIndex=1', () => {
        const result = sortOpportunities([make({ title: 'Solo', impact_rating: 'High' })])
        expect(result).toHaveLength(1)
        expect(result[0]).toEqual({
            opportunity: expect.objectContaining({ title: 'Solo' }),
            originalIndex: 0,
            printedIndex: 1,
        })
    })

    it('sorts by impact rating: High before Medium before Low', () => {
        const opps: Opportunity[] = [
            make({ title: 'Low item', impact_rating: 'Low' }),
            make({ title: 'High item', impact_rating: 'High' }),
            make({ title: 'Medium item', impact_rating: 'Medium' }),
        ]
        const result = sortOpportunities(opps)
        expect(result.map((entry) => entry.opportunity.title)).toEqual([
            'High item',
            'Medium item',
            'Low item',
        ])
    })

    it('preserves original order within the same impact rating (stable)', () => {
        const opps: Opportunity[] = [
            make({ title: 'High A', impact_rating: 'High' }),
            make({ title: 'High B', impact_rating: 'High' }),
            make({ title: 'High C', impact_rating: 'High' }),
        ]
        const result = sortOpportunities(opps)
        expect(result.map((entry) => entry.opportunity.title)).toEqual(['High A', 'High B', 'High C'])
    })

    it('preserves originalIndex through the sort', () => {
        const opps: Opportunity[] = [
            make({ title: 'idx-0', impact_rating: 'Low' }),
            make({ title: 'idx-1', impact_rating: 'High' }),
            make({ title: 'idx-2', impact_rating: 'Medium' }),
        ]
        const result = sortOpportunities(opps)
        expect(result.find((entry) => entry.opportunity.title === 'idx-1')?.originalIndex).toBe(1)
        expect(result.find((entry) => entry.opportunity.title === 'idx-0')?.originalIndex).toBe(0)
        expect(result.find((entry) => entry.opportunity.title === 'idx-2')?.originalIndex).toBe(2)
    })

    it('assigns sequential 1-based printedIndex values', () => {
        const opps: Opportunity[] = [
            make({ title: 'L', impact_rating: 'Low' }),
            make({ title: 'H', impact_rating: 'High' }),
            make({ title: 'M', impact_rating: 'Medium' }),
        ]
        const result = sortOpportunities(opps)
        expect(result.map((entry) => entry.printedIndex)).toEqual([1, 2, 3])
    })
})

describe('findByOriginalIndex', () => {
    const opps: Opportunity[] = [
        make({ title: 'idx-0', impact_rating: 'Low' }),
        make({ title: 'idx-1', impact_rating: 'High' }),
    ]
    const sorted = sortOpportunities(opps)

    it('returns the entry whose originalIndex matches', () => {
        const result = findByOriginalIndex(sorted, 1)
        expect(result?.opportunity.title).toBe('idx-1')
        expect(result?.printedIndex).toBe(1) // High sorted first
    })

    it('returns undefined when no entry matches', () => {
        expect(findByOriginalIndex(sorted, 99)).toBeUndefined()
    })
})
