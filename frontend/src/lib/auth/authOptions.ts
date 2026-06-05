import { NextAuthOptions } from 'next-auth'
import CredentialsProvider from 'next-auth/providers/credentials'

import { refreshCognitoSession, signInWithCognito } from '@/lib/auth/cognitoClient'

/** Refresh the idToken this many seconds before its actual expiry, to absorb
 *  clock skew and in-flight request latency. */
const REFRESH_SKEW_SECONDS = 60

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
                        refreshToken: result.refreshToken,
                        idTokenExpiresAt: Number(payload.exp),
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
            // Initial sign-in: persist identity + the Cognito tokens (incl. the
            // refresh token, server-side only) and the idToken expiry.
            if (user) {
                token.orgId = user.orgId
                token.role = user.role
                token.id = user.id
                token.idToken = user.idToken
                token.refreshToken = user.refreshToken
                token.idTokenExpiresAt = user.idTokenExpiresAt
                delete token.error
                return token
            }

            // Already in the terminal refresh-error state — don't keep calling
            // Cognito on every request. getBackendToken() returns null for this
            // token, so the user is en route to re-login (which clears the error
            // via the `if (user)` branch above).
            if (token.error === 'RefreshAccessTokenError') {
                return token
            }

            // Subsequent calls: the NextAuth session lives 8h but a Cognito
            // idToken only lasts 1h. Refresh it before expiry so server-side
            // `backendFetch` never sends an expired token (which the API rejects
            // with 401 "Token expired"). See cognito-token-refresh design D1/D3.
            const expiresAt = token.idTokenExpiresAt ?? 0
            const nowSeconds = Math.floor(Date.now() / 1000)
            if (nowSeconds < expiresAt - REFRESH_SKEW_SECONDS) {
                return token // still fresh — no refresh needed
            }
            if (!token.refreshToken) {
                token.error = 'RefreshAccessTokenError'
                return token
            }
            try {
                const refreshed = await refreshCognitoSession(token.refreshToken)
                const newExpiry = Number(decodeIdTokenPayload(refreshed.idToken).exp)
                // Guard against a malformed refreshed token (no `exp`): NaN would
                // make every future call think the token is expired and re-refresh
                // forever. Treat it as a refresh failure → re-login.
                if (!Number.isFinite(newExpiry)) {
                    throw new Error('Refreshed idToken is missing a valid exp claim')
                }
                token.idToken = refreshed.idToken
                token.idTokenExpiresAt = newExpiry
                delete token.error
            } catch {
                // Refresh token expired/revoked (30-day life), network failure, or
                // a malformed response → mark so getBackendToken() returns null and
                // the existing 401 → error-boundary → re-login path runs.
                token.error = 'RefreshAccessTokenError'
            }
            return token
        },
        async session({ session, token }) {
            if (session.user) {
                session.user.orgId = token.orgId ?? ''
                session.user.role = token.role ?? ''
                session.user.id = token.id ?? ''
                // idToken kept on JWT only (server-side) — not exposed to client useSession()
            }
            return session
        },
    },
    pages: { signIn: '/login' },
    secret: process.env.NEXTAUTH_SECRET,
    jwt: {
        maxAge: 8 * 60 * 60, // 8 hours
    },
}
