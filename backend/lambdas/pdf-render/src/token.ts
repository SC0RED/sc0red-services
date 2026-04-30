/**
 * Short-lived signed-URL token for the PDF render flow.
 *
 * Verbatim duplicate of `frontend/src/lib/pdf/token.ts` (the canonical
 * source). Kept in lockstep — the wire format and `PDF_TOKEN_SECRET`
 * env var name MUST agree across both copies. See
 * `openspec/specs/polished-pdf-export/spec.md`.
 *
 * The Lambda only needs `verifyToken` + `readSigningSecret` for the
 * defensive print-page validation pre-check, but `signToken` is kept
 * for symmetry and unit-test parity with the frontend module.
 */

import { createHmac, timingSafeEqual } from 'crypto'

export const TOKEN_TTL_SECONDS = 60
export const PDF_TOKEN_SECRET_ENV = 'PDF_TOKEN_SECRET'

export interface TokenPayload {
    analysisId: string
    orgId: string
    exp: number
}

export type VerifyResult =
    | { ok: true; payload: TokenPayload }
    | { ok: false; reason: VerifyFailureReason }

export type VerifyFailureReason =
    | 'missing_token'
    | 'missing_secret'
    | 'malformed'
    | 'signature_mismatch'
    | 'expired'
    | 'analysis_id_mismatch'

function toBase64Url(buffer: Buffer): string {
    return buffer.toString('base64').replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
}

function fromBase64Url(value: string): Buffer {
    const remainder = value.length % 4
    const padded = remainder === 0 ? value : value + '='.repeat(4 - remainder)
    return Buffer.from(padded.replace(/-/g, '+').replace(/_/g, '/'), 'base64')
}

interface SignInput {
    analysisId: string
    orgId: string
    nowSeconds?: number
    ttlSeconds?: number
}

export function signToken(
    { analysisId, orgId, nowSeconds, ttlSeconds }: SignInput,
    secret: string,
): string {
    if (!secret) throw new Error('signToken: secret is required')
    const now = nowSeconds ?? Math.floor(Date.now() / 1000)
    const ttl = ttlSeconds ?? TOKEN_TTL_SECONDS
    const payload: TokenPayload = { analysisId, orgId, exp: now + ttl }
    const encodedPayload = toBase64Url(Buffer.from(JSON.stringify(payload)))
    const signature = createHmac('sha256', secret).update(encodedPayload).digest()
    return `${encodedPayload}.${toBase64Url(signature)}`
}

export function verifyToken(
    token: string,
    expectedAnalysisId: string,
    secret: string,
): VerifyResult {
    if (!token) return { ok: false, reason: 'missing_token' }
    if (!secret) return { ok: false, reason: 'missing_secret' }

    const dotIndex = token.indexOf('.')
    if (dotIndex < 1 || dotIndex === token.length - 1) {
        return { ok: false, reason: 'malformed' }
    }
    const encodedPayload = token.slice(0, dotIndex)
    const encodedSignature = token.slice(dotIndex + 1)

    const expectedSig = createHmac('sha256', secret).update(encodedPayload).digest()
    let actualSig: Buffer
    try {
        actualSig = fromBase64Url(encodedSignature)
    } catch {
        return { ok: false, reason: 'malformed' }
    }
    if (expectedSig.length !== actualSig.length) return { ok: false, reason: 'signature_mismatch' }
    if (!timingSafeEqual(expectedSig, actualSig)) return { ok: false, reason: 'signature_mismatch' }

    let payload: TokenPayload
    try {
        const decoded = fromBase64Url(encodedPayload).toString('utf-8')
        const parsed = JSON.parse(decoded) as Partial<TokenPayload>
        if (
            typeof parsed.analysisId !== 'string' ||
            typeof parsed.orgId !== 'string' ||
            typeof parsed.exp !== 'number'
        ) {
            return { ok: false, reason: 'malformed' }
        }
        payload = parsed as TokenPayload
    } catch {
        return { ok: false, reason: 'malformed' }
    }

    if (payload.exp < Math.floor(Date.now() / 1000)) return { ok: false, reason: 'expired' }
    if (payload.analysisId !== expectedAnalysisId)
        return { ok: false, reason: 'analysis_id_mismatch' }

    return { ok: true, payload }
}

export function readSigningSecret(): string {
    const secret = process.env[PDF_TOKEN_SECRET_ENV]
    if (!secret) {
        throw new Error(
            `${PDF_TOKEN_SECRET_ENV} is not set. The PDF render flow requires the signing secret.`,
        )
    }
    return secret
}
