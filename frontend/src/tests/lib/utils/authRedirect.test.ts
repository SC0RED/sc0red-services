import { describe, it, expect } from 'vitest'

import { authPathWithCallback, resolvePostAuthPath } from '@/lib/utils/authRedirect'

describe('resolvePostAuthPath', () => {
    it('returns a same-origin relative callbackUrl', () => {
        expect(resolvePostAuthPath('/oauth/authorize?client_id=abc&state=xyz')).toBe(
            '/oauth/authorize?client_id=abc&state=xyz'
        )
    })

    it('falls back to /dashboard when no callbackUrl', () => {
        expect(resolvePostAuthPath(null)).toBe('/dashboard')
        expect(resolvePostAuthPath(undefined)).toBe('/dashboard')
        expect(resolvePostAuthPath('')).toBe('/dashboard')
    })

    it('rejects absolute URLs (open-redirect guard)', () => {
        expect(resolvePostAuthPath('https://evil.com/phish')).toBe('/dashboard')
        expect(resolvePostAuthPath('http://evil.com')).toBe('/dashboard')
    })

    it('rejects protocol-relative URLs', () => {
        expect(resolvePostAuthPath('//evil.com/phish')).toBe('/dashboard')
    })

    it('rejects values that do not start with a slash', () => {
        expect(resolvePostAuthPath('javascript:alert(1)')).toBe('/dashboard')
        expect(resolvePostAuthPath('dashboard')).toBe('/dashboard')
    })
})

describe('authPathWithCallback', () => {
    it('appends an encoded callbackUrl when present', () => {
        expect(authPathWithCallback('/signup', '/oauth/authorize?client_id=abc')).toBe(
            '/signup?callbackUrl=%2Foauth%2Fauthorize%3Fclient_id%3Dabc'
        )
    })

    it('returns the bare path when no callbackUrl', () => {
        expect(authPathWithCallback('/login', null)).toBe('/login')
        expect(authPathWithCallback('/login', undefined)).toBe('/login')
    })
})
