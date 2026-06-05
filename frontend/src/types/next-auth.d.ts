import 'next-auth'
import 'next-auth/jwt'

declare module 'next-auth' {
    interface User {
        id: string
        orgId: string
        role: string
        idToken?: string
        /**
         * @internal Login → jwt-callback handoff ONLY. Never written to
         * `session.user` by the session callback, so it is always `undefined`
         * on the client `useSession()`. Do not read it client-side.
         */
        refreshToken?: string
        /** @internal Login → jwt-callback handoff only (see refreshToken). */
        idTokenExpiresAt?: number
    }
    interface Session {
        user: User & { email: string; name?: string | null }
    }
}

declare module 'next-auth/jwt' {
    interface JWT {
        id?: string
        orgId?: string
        role?: string
        idToken?: string
        /** Cognito refresh token — server-side only, used to mint fresh idTokens. */
        refreshToken?: string
        /** Epoch seconds when the current idToken expires. */
        idTokenExpiresAt?: number
        /** Set to "RefreshAccessTokenError" when a refresh fails → force re-login. */
        error?: string
    }
}
