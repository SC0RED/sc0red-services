/**
 * Creates an RS256 Cognito-like ID token for E2E tests.
 *
 * Uses the test private key from scripts/e2e-keys/ (same key that
 * the mock JWKS endpoint serves as the public key).
 */

import { readFileSync } from 'fs'
import { join } from 'path'
import { SignJWT, importPKCS8 } from 'jose'

const PRIVATE_KEY_PATH = join(__dirname, '..', '..', '..', 'scripts', 'e2e-keys', 'private_key.pem')

export async function createIdToken(
    user: {
        id: string
        email: string
        name: string
        orgId: string
        role: string
    },
    options: { expiresIn?: string } = {}
): Promise<string> {
    const privateKeyPem = readFileSync(PRIVATE_KEY_PATH, 'utf-8')
    const privateKey = await importPKCS8(privateKeyPem, 'RS256')

    const builder = new SignJWT({
        sub: user.id,
        email: user.email,
        name: user.name,
        'custom:org_id': user.orgId,
        'custom:role': user.role,
        'custom:legacy_user_id': user.id,
    })
        .setProtectedHeader({ alg: 'RS256', kid: 'e2e-test-key' })
        .setIssuedAt()

    // Allow creating already-expired tokens for session expiry tests.
    // setExpirationTime only accepts future times, so for expired tokens
    // we manually set exp to a past timestamp.
    const expiresIn = options.expiresIn || '8h'
    if (expiresIn.startsWith('-')) {
        const seconds = parseDuration(expiresIn.slice(1))
        builder.setExpirationTime(Math.floor(Date.now() / 1000) - seconds)
    } else {
        builder.setExpirationTime(expiresIn)
    }

    return builder.sign(privateKey)
}

/** Parse a duration string like '1h', '30m', '60s' into seconds. */
function parseDuration(duration: string): number {
    const match = duration.match(/^(\d+)([hms])$/)
    if (!match) throw new Error(`Invalid duration: ${duration}`)
    const value = parseInt(match[1], 10)
    const unit = match[2]
    if (unit === 'h') return value * 3600
    if (unit === 'm') return value * 60
    return value
}
