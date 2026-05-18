/**
 * Test-only token signer for the PDF render flow.
 *
 * Production token signing lives in the Python backend
 * (`backend/src/utilities/pdf_token.py`); the TypeScript runtime only
 * needs to *verify* tokens, never mint them. But verifier tests still
 * need to construct valid tokens to exercise the verify path —
 * that's what this helper is for.
 *
 * The implementation mirrors `verifyToken`'s payload + base64url
 * encoding so the round-trip produces a token `verifyToken` accepts.
 * Kept in `tests/helpers/` (NOT `src/`) so production bundles never
 * ship the signing primitive.
 */

import { createHmac } from 'crypto'

export const TOKEN_TTL_SECONDS_FOR_TEST = 60

interface SignInput {
    analysisId: string
    orgId: string
    /** Override the current time (unix seconds). */
    nowSeconds?: number
    /** Override the TTL. */
    ttlSeconds?: number
}

function toBase64Url(buffer: Buffer): string {
    return buffer.toString('base64').replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
}

export function signTokenForTest(
    { analysisId, orgId, nowSeconds, ttlSeconds }: SignInput,
    secret: string,
): string {
    if (!secret) throw new Error('signTokenForTest: secret is required')
    const now = nowSeconds ?? Math.floor(Date.now() / 1000)
    const ttl = ttlSeconds ?? TOKEN_TTL_SECONDS_FOR_TEST
    const payload = { analysisId, orgId, exp: now + ttl }
    const encodedPayload = toBase64Url(Buffer.from(JSON.stringify(payload)))
    const signature = createHmac('sha256', secret).update(encodedPayload).digest()
    return `${encodedPayload}.${toBase64Url(signature)}`
}
