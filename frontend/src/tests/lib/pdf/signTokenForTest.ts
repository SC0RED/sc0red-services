/**
 * Test-only token signer for the PDF render flow.
 *
 * Production signing lives in the Python backend (the print route +
 * Lambda only ever *verify* tokens server-side). Verifier tests still
 * need to construct valid tokens to exercise the verify path —
 * that's this helper.
 *
 * Implementation mirrors `verifyToken`'s payload + base64url encoding
 * so the round-trip produces a token `verifyToken` accepts.
 */

import { createHmac } from 'crypto'

export const TOKEN_TTL_SECONDS_FOR_TEST = 60

interface SignInput {
    analysisId: string
    orgId: string
    nowSeconds?: number
    ttlSeconds?: number
}

function toBase64Url(buffer: Buffer): string {
    return buffer.toString('base64').replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
}

export function signTokenForTest(
    { analysisId, orgId, nowSeconds, ttlSeconds }: SignInput,
    secret: string
): string {
    if (!secret) throw new Error('signTokenForTest: secret is required')
    const now = nowSeconds ?? Math.floor(Date.now() / 1000)
    const ttl = ttlSeconds ?? TOKEN_TTL_SECONDS_FOR_TEST
    const payload = { analysisId, orgId, exp: now + ttl }
    const encodedPayload = toBase64Url(Buffer.from(JSON.stringify(payload)))
    const signature = createHmac('sha256', secret).update(encodedPayload).digest()
    return `${encodedPayload}.${toBase64Url(signature)}`
}
