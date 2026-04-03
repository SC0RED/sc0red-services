import { describe, it, expect } from 'vitest'

import {
    getRiskTier,
    getRiskTierLabel,
    getRiskColor,
    getImpactColor,
    calculateOverallScore,
} from '@/lib/utils/riskUtils'

describe('getRiskTier', () => {
    it('returns low for score 0', () => {
        expect(getRiskTier(0)).toBe('low')
    })

    it('returns low for score 3 (boundary)', () => {
        expect(getRiskTier(3)).toBe('low')
    })

    it('returns moderate for score 3.1', () => {
        expect(getRiskTier(3.1)).toBe('moderate')
    })

    it('returns moderate for score 6 (boundary)', () => {
        expect(getRiskTier(6)).toBe('moderate')
    })

    it('returns high for score 6.1', () => {
        expect(getRiskTier(6.1)).toBe('high')
    })

    it('returns high for score 8 (boundary)', () => {
        expect(getRiskTier(8)).toBe('high')
    })

    it('returns critical for score 8.1', () => {
        expect(getRiskTier(8.1)).toBe('critical')
    })

    it('returns critical for score 10', () => {
        expect(getRiskTier(10)).toBe('critical')
    })
})

describe('getRiskTierLabel', () => {
    it('returns "Low Risk" for low', () => {
        expect(getRiskTierLabel('low')).toBe('Low Risk')
    })

    it('returns "Moderate Risk" for moderate', () => {
        expect(getRiskTierLabel('moderate')).toBe('Moderate Risk')
    })

    it('returns "High Risk" for high', () => {
        expect(getRiskTierLabel('high')).toBe('High Risk')
    })

    it('returns "Critical Risk" for critical', () => {
        expect(getRiskTierLabel('critical')).toBe('Critical Risk')
    })

    it('falls back to the raw tier string for unknown values', () => {
        expect(getRiskTierLabel('unknown')).toBe('unknown')
    })
})

describe('getRiskColor', () => {
    it('returns correct CSS var for low', () => {
        expect(getRiskColor('low')).toBe('var(--risk-low)')
    })

    it('returns correct CSS var for moderate', () => {
        expect(getRiskColor('moderate')).toBe('var(--risk-moderate)')
    })

    it('returns correct CSS var for high', () => {
        expect(getRiskColor('high')).toBe('var(--risk-high)')
    })

    it('returns correct CSS var for critical', () => {
        expect(getRiskColor('critical')).toBe('var(--risk-critical)')
    })

    it('returns fallback for unknown tier', () => {
        expect(getRiskColor('unknown')).toBe('var(--text-secondary)')
    })
})

describe('getImpactColor', () => {
    it('returns green for High impact', () => {
        expect(getImpactColor('High')).toBe('var(--risk-low)')
    })

    it('returns amber for Medium impact', () => {
        expect(getImpactColor('Medium')).toBe('var(--risk-moderate)')
    })

    it('returns secondary for Low impact', () => {
        expect(getImpactColor('Low')).toBe('var(--text-secondary)')
    })

    it('returns fallback for unknown impact', () => {
        expect(getImpactColor('Critical')).toBe('var(--text-secondary)')
    })
})

describe('calculateOverallScore', () => {
    it('returns 0 for empty array', () => {
        expect(calculateOverallScore([])).toBe(0)
    })

    it('returns the score for a single item', () => {
        expect(calculateOverallScore([{ score: 5 }])).toBe(5)
    })

    it('returns the rounded average for multiple items', () => {
        expect(calculateOverallScore([{ score: 3 }, { score: 6 }, { score: 9 }])).toBe(6)
    })

    it('rounds to one decimal place', () => {
        expect(calculateOverallScore([{ score: 3 }, { score: 4 }])).toBe(3.5)
    })

    it('handles fractional scores correctly', () => {
        expect(calculateOverallScore([{ score: 1 }, { score: 2 }, { score: 3 }])).toBe(2)
    })
})
