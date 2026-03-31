import { NextAuthOptions } from 'next-auth'
import CredentialsProvider from 'next-auth/providers/credentials'

import { signInWithCognito } from '@/lib/auth/cognitoClient'

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
                    return null
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
                session.user.idToken = token.idToken
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
