import { describe, it, expect, afterEach } from 'vitest'

import { readInternalApiKey, readSigningSecret } from '@/lib/pdf/secretSource'

afterEach(() => {
    delete process.env.PDF_TOKEN_SECRET
    delete process.env.INTERNAL_API_KEY
})

describe('readSigningSecret', () => {
    it('returns the env var when set', () => {
        process.env.PDF_TOKEN_SECRET = 'present'
        expect(readSigningSecret()).toBe('present')
    })

    it('throws a clear error when missing', () => {
        delete process.env.PDF_TOKEN_SECRET
        expect(() => readSigningSecret()).toThrow(/PDF_TOKEN_SECRET is not set/)
    })
})

describe('readInternalApiKey', () => {
    it('returns the env var when set', () => {
        process.env.INTERNAL_API_KEY = 'present'
        expect(readInternalApiKey()).toBe('present')
    })

    it('throws a clear error when missing', () => {
        delete process.env.INTERNAL_API_KEY
        expect(() => readInternalApiKey()).toThrow(/INTERNAL_API_KEY is not set/)
    })
})
