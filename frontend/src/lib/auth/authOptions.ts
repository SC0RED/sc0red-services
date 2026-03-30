import { NextAuthOptions } from 'next-auth'
import CredentialsProvider from 'next-auth/providers/credentials'

import { signInWithCognito } from '@/lib/auth/cognitoClient'
import { BACKEND_URL } from '@/lib/config'

/**
 * Decode a Cognito ID token's payload without verification.
 * Verification is done by the backend against JWKS.
 */
function decodeIdTokenPayload(idToken: string): Record<string, string> {
    const payload = idToken.split('.')[1]
    return JSON.parse(Buffer.from(payload, 'base64url').toString())
}

export const authOptions: NextAuthOptions = {
    providers: [
        CredentialsProvider({
            name: 'credentials',
            credentials: {
                email: { label: 'Email', type: 'email' },
                password: { label: 'Password', type: 'password' },
            },
            async authorize(credentials) {
                if (!credentials?.email || !credentials?.password) return null

                try {
                    // Try Cognito first
                    const result = await signInWithCognito(credentials.email, credentials.password)

                    // NEW_PASSWORD_REQUIRED = invited user needs to set password
                    // This is handled by the accept-invite page, not the login flow
                    if (result.challengeName === 'NEW_PASSWORD_REQUIRED') return null

                    const payload = decodeIdTokenPayload(result.idToken)

                    return {
                        id: payload['custom:legacy_user_id'] || payload.sub,
                        email: payload.email,
                        name: payload.name || '',
                        orgId: payload['custom:org_id'] || '',
                        role: payload['custom:role'] || 'analyst',
                        idToken: result.idToken,
                    }
                } catch {
                    // Cognito auth failed — try legacy backend login as fallback
                    // This handles the window where a user hasn't been migrated yet
                    try {
                        return await legacyLogin(credentials.email, credentials.password)
                    } catch {
                        return null
                    }
                }
            },
        }),
    ],
    session: { strategy: 'jwt' },
    callbacks: {
        async jwt({ token, user }) {
            if (user) {
                token.orgId = user.orgId
                token.role = user.role
                token.id = user.id
                token.idToken = user.idToken
            }
            return token
        },
        async session({ session, token }) {
            if (session.user) {
                session.user.orgId = token.orgId ?? ''
                session.user.role = token.role ?? ''
                session.user.id = token.id ?? ''
            }
            return session
        },
    },
    pages: { signIn: '/login' },
    secret: process.env.NEXTAUTH_SECRET,
    jwt: {
        maxAge: 60 * 60, // 1 hour (matches Cognito token validity)
    },
}

/**
 * Legacy login via Python backend — fallback for users not yet in Cognito.
 * Will be removed in Phase 5.
 */
async function legacyLogin(
    email: string,
    password: string
): Promise<{ id: string; email: string; name: string; orgId: string; role: string } | null> {
    const response = await fetch(`${BACKEND_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
    })

    if (!response.ok) return null

    const data = (await response.json()) as {
        success: boolean
        user: { id: string; email: string; name: string; orgId: string; role: string }
    }
    if (!data.success || !data.user) return null

    return {
        id: data.user.id,
        email: data.user.email,
        name: data.user.name,
        orgId: data.user.orgId,
        role: data.user.role,
    }
}
