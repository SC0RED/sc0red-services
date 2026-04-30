import { describe, it, expect } from 'vitest'

import {
    PDF_TOKEN_SECRET_ENV,
    TOKEN_TTL_SECONDS,
    readSigningSecret,
    signToken,
    verifyToken,
} from '@/lib/pdf/token'

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
        const parts = token.split('.')
        expect(parts).toHaveLength(2)
        // base64url alphabet only — no `+`, `/`, `=`.
        for (const part of parts) {
            expect(part).toMatch(/^[A-Za-z0-9_-]+$/)
        }
    })
})

describe('verifyToken — rejection paths', () => {
    it('rejects an empty token', () => {
        const result = verifyToken('', 'a-1', SECRET)
        expect(result).toEqual({ ok: false, reason: 'missing_token' })
    })

    it('rejects when the secret is empty', () => {
        const token = signToken({ analysisId: 'a-1', orgId: 'org-1' }, SECRET)
        const result = verifyToken(token, 'a-1', '')
        expect(result).toEqual({ ok: false, reason: 'missing_secret' })
    })

    it('rejects a malformed token (no dot)', () => {
        const result = verifyToken('not-a-token', 'a-1', SECRET)
        expect(result).toEqual({ ok: false, reason: 'malformed' })
    })

    it('rejects a token signed with a different secret', () => {
        const token = signToken({ analysisId: 'a-1', orgId: 'org-1' }, SECRET)
        const result = verifyToken(token, 'a-1', 'different-secret-of-equal-length-padding')
        expect(result).toEqual({ ok: false, reason: 'signature_mismatch' })
    })

    it('rejects a tampered payload (signature mismatch)', () => {
        const token = signToken({ analysisId: 'a-1', orgId: 'org-1' }, SECRET)
        const [, sig] = token.split('.')
        const tamperedPayload = Buffer.from(
            JSON.stringify({ analysisId: 'a-EVIL', orgId: 'org-1', exp: 9999999999 })
        )
            .toString('base64')
            .replace(/=/g, '')
            .replace(/\+/g, '-')
            .replace(/\//g, '_')
        const tampered = `${tamperedPayload}.${sig}`
        const result = verifyToken(tampered, 'a-EVIL', SECRET)
        expect(result.ok).toBe(false)
        if (!result.ok) expect(result.reason).toBe('signature_mismatch')
    })

    it('rejects an expired token', () => {
        // Sign with `nowSeconds` 120s in the past so the +60s TTL is already gone.
        const past = Math.floor(Date.now() / 1000) - 2 * TOKEN_TTL_SECONDS
        const token = signToken({ analysisId: 'a-1', orgId: 'org-1', nowSeconds: past }, SECRET)
        const result = verifyToken(token, 'a-1', SECRET)
        expect(result).toEqual({ ok: false, reason: 'expired' })
    })

    it('rejects when the analysisId in the token does not match the URL', () => {
        const token = signToken({ analysisId: 'a-1', orgId: 'org-1' }, SECRET)
        const result = verifyToken(token, 'a-2', SECRET)
        expect(result).toEqual({ ok: false, reason: 'analysis_id_mismatch' })
    })

    it('rejects gibberish in the signature segment', () => {
        const [payload] = signToken({ analysisId: 'a-1', orgId: 'org-1' }, SECRET).split('.')
        const result = verifyToken(`${payload}.@@@bad@@@`, 'a-1', SECRET)
        expect(result.ok).toBe(false)
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

    it('throws a clear error when missing', () => {
        delete process.env[PDF_TOKEN_SECRET_ENV]
        expect(() => readSigningSecret()).toThrow(/PDF_TOKEN_SECRET is not set/)
    })
})
