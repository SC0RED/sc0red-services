import { describe, expect, it } from 'vitest'

import { normalizeUserUrl, prettifyUrl } from '@/lib/utils/url'

describe('prettifyUrl', () => {
    it('strips scheme and trailing slash', () => {
        expect(prettifyUrl('https://perotjain.com/')).toBe('perotjain.com')
    })

    it('keeps path when present', () => {
        expect(prettifyUrl('https://www.example.com/firms/123/')).toBe('www.example.com/firms/123')
    })

    it('falls back to the original string when URL parsing fails', () => {
        expect(prettifyUrl('not a url')).toBe('not a url')
    })
})

describe('normalizeUserUrl', () => {
    it('auto-prepends https:// for bare hostnames', () => {
        // The original Diagnostic Tool Feedback #1 case — Zack typed
        // `www.sc0red.com` and got a generic browser rejection. The
        // normaliser should accept it and produce a fetchable URL.
        expect(normalizeUserUrl('www.sc0red.com')).toEqual({ url: 'https://www.sc0red.com/' })
    })

    it('auto-prepends https:// for two-label hostnames', () => {
        expect(normalizeUserUrl('stripe.com')).toEqual({ url: 'https://stripe.com/' })
    })

    it('preserves an explicit https:// scheme', () => {
        expect(normalizeUserUrl('https://example.com/path')).toEqual({
            url: 'https://example.com/path',
        })
    })

    it('preserves an explicit http:// scheme — does not silently upgrade', () => {
        // Some intranet / staging targets legitimately need plain HTTP;
        // silently rewriting to HTTPS would mask that signal. The scrape
        // pipeline owns the real fetch decision.
        expect(normalizeUserUrl('http://example.com')).toEqual({ url: 'http://example.com/' })
    })

    it('trims whitespace before parsing', () => {
        expect(normalizeUserUrl('  example.com  ')).toEqual({ url: 'https://example.com/' })
    })

    it('rejects empty input with a friendly error', () => {
        const result = normalizeUserUrl('   ')
        expect(result).toEqual({ error: 'Please enter a website URL (e.g. example.com)' })
    })

    it('rejects single-word hostnames (no dot)', () => {
        // `localhost`, `foo`, etc. parse as valid URLs but the scrape
        // pipeline can't fetch them — catch them at the form layer.
        const result = normalizeUserUrl('localhost')
        expect(result).toEqual({ error: 'Please enter a website URL (e.g. example.com)' })
    })

    it('rejects pure garbage with the same friendly error', () => {
        const result = normalizeUserUrl('not a url at all')
        expect(result).toEqual({ error: 'Please enter a website URL (e.g. example.com)' })
    })

    it('handles a URL that already includes a path + query', () => {
        expect(normalizeUserUrl('foo.com/bar?baz=1')).toEqual({
            url: 'https://foo.com/bar?baz=1',
        })
    })
})
