import { describe, it, expect } from 'vitest'

import {
    buildContentDisposition,
    buildPdfFilename,
    formatAnalysisDate,
    sanitiseCompanyName,
} from '@/lib/pdf/filename'

describe('formatAnalysisDate', () => {
    it('formats yyyy-MM-dd in UTC', () => {
        expect(formatAnalysisDate(new Date('2026-04-30T15:00:00Z'))).toBe('2026-04-30')
    })

    it('falls back to today when input is invalid', () => {
        expect(formatAnalysisDate('not-a-date')).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    })

    it('defaults to today when no input is provided', () => {
        expect(formatAnalysisDate()).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    })
})

describe('sanitiseCompanyName', () => {
    it('strips slashes and colons', () => {
        expect(sanitiseCompanyName('Acme/Corp:Inc')).toBe('AcmeCorpInc')
    })

    it('strips Windows-invalid characters', () => {
        expect(sanitiseCompanyName('a<b>c"d|e?f*g')).toBe('abcdefg')
    })

    it('collapses runs of whitespace', () => {
        expect(sanitiseCompanyName('Acme    Corp\t\nInc')).toBe('Acme Corp Inc')
    })

    it('falls back to "Analysis" when all characters are stripped', () => {
        expect(sanitiseCompanyName('///')).toBe('Analysis')
    })

    it('preserves UTF-8 characters that are filename-safe', () => {
        expect(sanitiseCompanyName('Café Société')).toBe('Café Société')
    })
})

describe('buildPdfFilename', () => {
    it('builds the canonical "Company - AI Risk Report - YYYY-MM-DD.pdf" shape', () => {
        const filename = buildPdfFilename('Acme Corp', '2026-04-30T00:00:00Z')
        expect(filename).toBe('Acme Corp - AI Risk Report - 2026-04-30.pdf')
    })

    it('caps total length at 80 characters', () => {
        const longName = 'A'.repeat(200)
        const filename = buildPdfFilename(longName, '2026-04-30T00:00:00Z')
        expect(filename.length).toBeLessThanOrEqual(80)
    })

    it('always ends with .pdf', () => {
        const filename = buildPdfFilename('A'.repeat(200), '2026-04-30T00:00:00Z')
        expect(filename).toMatch(/\.pdf$/)
    })
})

describe('buildContentDisposition', () => {
    it('produces both filename and filename* parameters', () => {
        const header = buildContentDisposition('Acme - AI Risk Report - 2026-04-30.pdf')
        expect(header).toContain('attachment;')
        expect(header).toMatch(/filename="[^"]+"/)
        expect(header).toMatch(/filename\*=UTF-8''/)
    })

    it('encodes non-ASCII in the filename* parameter', () => {
        const header = buildContentDisposition('Café - AI Risk Report - 2026-04-30.pdf')
        expect(header).toMatch(/filename\*=UTF-8''Caf%C3%A9/)
    })

    it('replaces non-ASCII with underscores in the ASCII fallback', () => {
        const header = buildContentDisposition('Café Test.pdf')
        expect(header).toMatch(/filename="Caf_ Test\.pdf"/)
    })
})
