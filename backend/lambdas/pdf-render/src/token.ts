/**
 * Short-lived signed-URL token for the PDF render flow.
 *
 * The Python backend's async export endpoint mints a token, embeds it
 * in the URL `?t=...` that the headless browser navigates to. The
 * `/print/{analysisId}` route validates the token before rendering.
 *
 * Tokens are HMAC-SHA256 over a JSON payload `{ analysisId, orgId, exp }`
 * with a 60-second TTL. The wire format is `base64url(payload).base64url(sig)`,
 * matching the JWS-Compact shape but without the JOSE header overhead.
 *
 * IMPORTANT: this module is the CANONICAL VERIFY implementation. The
 * SIGN side was retired from TypeScript in Phase 4 of
 * `async-pdf-export-with-cache` — the Python backend now owns signing
 * (`backend/src/utilities/pdf_token.py`). Both verifies (this module
 * + `frontend/src/lib/pdf/token.ts`) MUST stay byte-identical: the
 * `npm run check-token-sync` step in CI fails the diff otherwise.
 */

import { createHmac, timingSafeEqual } from 'crypto'

export const TOKEN_TTL_SECONDS = 60

export interface TokenPayload {
    /** The analysis the token authorises rendering for. */
    analysisId: string
    /** The org of the user who minted the token (carries through for audit). */
    orgId: string
    /** Unix epoch seconds at which the token stops being valid. */
    exp: number
}

export type VerifyResult = { ok: true; payload: TokenPayload } | { ok: false; reason: VerifyFailureReason }

export type VerifyFailureReason =
    | 'missing_token'
    | 'missing_secret'
    | 'malformed'
    | 'signature_mismatch'
    | 'expired'
    | 'analysis_id_mismatch'

function fromBase64Url(value: string): Buffer {
    const remainder = value.length % 4
    const padded = remainder === 0 ? value : value + '='.repeat(4 - remainder)
    return Buffer.from(padded.replace(/-/g, '+').replace(/_/g, '/'), 'base64')
}

/**
 * Verify a token against the expected analysis. Returns a discriminated
 * result so the caller can map the failure reason to the correct HTTP
 * status (401 for any failure here is fine — the reason is for logs).
 */
export function verifyToken(token: string, expectedAnalysisId: string, secret: string): VerifyResult {
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
    if (payload.analysisId !== expectedAnalysisId) return { ok: false, reason: 'analysis_id_mismatch' }

    return { ok: true, payload }
}
