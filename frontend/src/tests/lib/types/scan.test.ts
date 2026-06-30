import { describe, it, expect } from 'vitest'

import { hasAnalyzableUrl, withDefaultSelection } from '@/lib/types/scan'

describe('hasAnalyzableUrl', () => {
    it('accepts http(s) URLs', () => {
        expect(hasAnalyzableUrl('https://acme.com')).toBe(true)
        expect(hasAnalyzableUrl('http://acme.com')).toBe(true)
    })

    it('rejects empty or non-http values', () => {
        expect(hasAnalyzableUrl('')).toBe(false)
        expect(hasAnalyzableUrl('acme.com')).toBe(false)
        expect(hasAnalyzableUrl('ftp://acme.com')).toBe(false)
    })
})

describe('withDefaultSelection', () => {
    it('pre-selects a site company with a URL', () => {
        const c = withDefaultSelection({
            name: 'Acme',
            url: 'https://acme.com',
            description: '',
            source: 'site',
        })
        expect(c.selected).toBe(true)
    })

    it('does NOT pre-select a web_search company even with a URL', () => {
        const c = withDefaultSelection({
            name: 'Beta',
            url: 'https://beta.com',
            description: '',
            source: 'web_search',
        })
        expect(c.selected).toBe(false)
    })

    it('does NOT pre-select a url-less company (would be silently dropped at confirm)', () => {
        const c = withDefaultSelection({ name: 'NoUrl Co', url: '', description: '', source: 'site' })
        expect(c.selected).toBe(false)
    })

    it('does NOT pre-select a realized (exited) company', () => {
        const c = withDefaultSelection({
            name: 'Exited Co',
            url: 'https://exited.com',
            description: '',
            source: 'site',
            status: 'realized',
        })
        expect(c.selected).toBe(false)
    })

    it('pre-selects a current company (status set, not realized)', () => {
        const c = withDefaultSelection({
            name: 'Active Co',
            url: 'https://active.com',
            description: '',
            source: 'site',
            status: 'current',
        })
        expect(c.selected).toBe(true)
    })
})
