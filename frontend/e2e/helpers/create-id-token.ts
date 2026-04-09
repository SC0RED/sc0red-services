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

export async function createIdToken(user: {
    id: string
    email: string
    name: string
    orgId: string
    role: string
}): Promise<string> {
    const privateKeyPem = readFileSync(PRIVATE_KEY_PATH, 'utf-8')
    const privateKey = await importPKCS8(privateKeyPem, 'RS256')

    const token = await new SignJWT({
        sub: user.id,
        email: user.email,
        name: user.name,
        'custom:org_id': user.orgId,
        'custom:role': user.role,
        'custom:legacy_user_id': user.id,
    })
        .setProtectedHeader({ alg: 'RS256', kid: 'e2e-test-key' })
        .setExpirationTime('8h')
        .setIssuedAt()
        .sign(privateKey)

    return token
}
