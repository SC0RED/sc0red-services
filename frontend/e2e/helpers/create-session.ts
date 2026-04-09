/**
 * Creates a NextAuth-compatible encrypted session cookie for E2E tests.
 *
 * NextAuth v4 uses jose EncryptJWT with:
 * - Algorithm: dir (direct key agreement)
 * - Encryption: A256GCM
 * - Key: derived from NEXTAUTH_SECRET via HKDF
 *
 * This replicates the NextAuth encode() function to create a valid
 * session token without going through the Cognito login flow.
 */

import { EncryptJWT } from 'jose'
import { hkdf } from '@panva/hkdf'

const NEXTAUTH_SECRET = process.env.NEXTAUTH_SECRET || 'dev-secret-minimum-32-characters-long'

async function getDerivedEncryptionKey(secret: string): Promise<Uint8Array> {
    return await hkdf('sha256', secret, '', 'NextAuth.js Generated Encryption Key', 32)
}

interface SessionUser {
    id: string
    email: string
    name: string
    orgId: string
    role: string
    idToken: string
}

export async function createSessionToken(user: SessionUser): Promise<string> {
    const encryptionKey = await getDerivedEncryptionKey(NEXTAUTH_SECRET)

    const token = await new EncryptJWT({
        sub: user.id,
        email: user.email,
        name: user.name,
        id: user.id,
        orgId: user.orgId,
        role: user.role,
        idToken: user.idToken,
        iat: Math.floor(Date.now() / 1000),
        exp: Math.floor(Date.now() / 1000) + 8 * 60 * 60, // 8 hours
    })
        .setProtectedHeader({ alg: 'dir', enc: 'A256GCM' })
        .setIssuedAt()
        .setExpirationTime('8h')
        .encrypt(encryptionKey)

    return token
}
