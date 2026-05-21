import { describe, it, expect } from 'vitest'

import { capitalise } from '@/lib/utils/stringUtils'

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
