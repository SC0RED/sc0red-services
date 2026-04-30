import { describe, expect, it } from 'vitest'

import {
    PDF_TOKEN_SECRET_ENV,
    TOKEN_TTL_SECONDS,
    readSigningSecret,
    signToken,
    verifyToken,
} from '../src/token'

const SECRET = 'test-secret-32-bytes-of-randomness-please'

describe('signToken / verifyToken — round-trip', () => {
    it('signs a token that verifies against the same analysisId + secret', () => {
        const token = signToken({ analysisId: 'a-1', orgId: 'org-1' }, SECRET)
        const result = verifyToken(token, 'a-1', SECRET)
        expect(result.ok).toBe(true)
        if (result.ok) {
            expect(result.payload.analysisId).toBe('a-1')
            expect(result.payload.orgId).toBe('org-1')
        }
    })

    it('produces tokens shaped like base64url(payload).base64url(sig)', () => {
        const token = signToken({ analysisId: 'a-1', orgId: 'org-1' }, SECRET)
        expect(token.split('.')).toHaveLength(2)
        for (const part of token.split('.')) {
            expect(part).toMatch(/^[A-Za-z0-9_-]+$/)
        }
    })
})

describe('verifyToken — rejection paths', () => {
    it('rejects missing tokens', () => {
        expect(verifyToken('', 'a-1', SECRET)).toEqual({ ok: false, reason: 'missing_token' })
    })

    it('rejects when secret is missing', () => {
        const token = signToken({ analysisId: 'a-1', orgId: 'org-1' }, SECRET)
        expect(verifyToken(token, 'a-1', '')).toEqual({ ok: false, reason: 'missing_secret' })
    })

    it('rejects malformed tokens', () => {
        expect(verifyToken('garbage', 'a-1', SECRET)).toEqual({ ok: false, reason: 'malformed' })
    })

    it('rejects tokens signed with a different secret', () => {
        const token = signToken({ analysisId: 'a-1', orgId: 'org-1' }, SECRET)
        expect(verifyToken(token, 'a-1', 'other-secret-of-equal-length-padding-x')).toEqual({
            ok: false,
            reason: 'signature_mismatch',
        })
    })

    it('rejects expired tokens', () => {
        const past = Math.floor(Date.now() / 1000) - 2 * TOKEN_TTL_SECONDS
        const token = signToken({ analysisId: 'a-1', orgId: 'org-1', nowSeconds: past }, SECRET)
        expect(verifyToken(token, 'a-1', SECRET)).toEqual({ ok: false, reason: 'expired' })
    })

    it('rejects tokens for a different analysisId', () => {
        const token = signToken({ analysisId: 'a-1', orgId: 'org-1' }, SECRET)
        expect(verifyToken(token, 'a-OTHER', SECRET)).toEqual({
            ok: false,
            reason: 'analysis_id_mismatch',
        })
    })
})

describe('readSigningSecret', () => {
    it('returns the env var when set', () => {
        process.env[PDF_TOKEN_SECRET_ENV] = 'present'
        try {
            expect(readSigningSecret()).toBe('present')
        } finally {
            delete process.env[PDF_TOKEN_SECRET_ENV]
        }
    })

    it('throws when missing', () => {
        delete process.env[PDF_TOKEN_SECRET_ENV]
        expect(() => readSigningSecret()).toThrow(/PDF_TOKEN_SECRET is not set/)
    })
})
