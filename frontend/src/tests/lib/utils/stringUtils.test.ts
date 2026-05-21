import { describe, it, expect } from 'vitest'

import { capitalise, truncate } from '@/lib/utils/stringUtils'

describe('capitalise', () => {
    it('uppercases the first character', () => {
        expect(capitalise('high')).toBe('High')
        expect(capitalise('medium')).toBe('Medium')
        expect(capitalise('low')).toBe('Low')
    })

    it('returns empty string unchanged', () => {
        expect(capitalise('')).toBe('')
    })

    it('leaves already-capitalised input unchanged', () => {
        expect(capitalise('High')).toBe('High')
    })

    it('only touches the first character — rest of the string is preserved verbatim', () => {
        expect(capitalise('hELLO')).toBe('HELLO')
    })

    it('handles a single-character input', () => {
        expect(capitalise('a')).toBe('A')
    })
})

describe('truncate', () => {
    it('returns short input unchanged', () => {
        expect(truncate('Short', 22)).toBe('Short')
    })

    it('returns input at the exact budget unchanged', () => {
        // 22 chars; budget is 22 → no ellipsis appended.
        const exact = 'a'.repeat(22)
        expect(truncate(exact, 22)).toBe(exact)
    })

    it('truncates long input and appends an ellipsis', () => {
        expect(truncate('Deploy AI churn prediction model', 22)).toBe('Deploy AI churn predi…')
    })

    it('keeps the output length at or below the maxChars budget', () => {
        const result = truncate('Deploy AI churn prediction model end-to-end', 22)
        expect(result.length).toBeLessThanOrEqual(22)
        expect(result.endsWith('…')).toBe(true)
    })

    it('trims trailing whitespace before the ellipsis', () => {
        // The naive cut would land mid-word at "Build a longer ph" — but
        // if the cut lands on a space we want "Build a longer p…" not
        // "Build a longer p …".
        expect(truncate('Build a longer phrase  here', 18)).not.toMatch(/ …$/)
    })

    it('returns empty string unchanged', () => {
        expect(truncate('', 22)).toBe('')
    })

    it('returns input unchanged when maxChars is zero or negative', () => {
        // Defensive: callers don't have to range-check the budget.
        expect(truncate('Hello', 0)).toBe('Hello')
        expect(truncate('Hello', -5)).toBe('Hello')
    })
})
