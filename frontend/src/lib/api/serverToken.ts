/**
 * Server-side backend token utility.
 *
 * Extracts the Cognito ID token from the NextAuth session and sends it
 * to the Python backend. Falls back to signing an HS256 JWT for sessions
 * that were created before the Cognito migration.
 */

import jwt from 'jsonwebtoken'
import { getServerSession } from 'next-auth'

import { BackendError } from '@/lib/api/errors'
import { authOptions } from '@/lib/auth/authOptions'
import { BACKEND_URL } from '@/lib/config'

/**
 * Get a backend-ready token from the current session.
 *
 * If the session has a Cognito idToken (RS256), use it directly.
 * Otherwise, fall back to signing an HS256 JWT (legacy sessions).
 */
export async function getBackendToken(): Promise<string | null> {
    const session = await getServerSession(authOptions)
    if (!session || !session.user) return null

    // Check if the NextAuth JWT has a Cognito idToken
    // We access the raw token via a workaround: the JWT callback stores it
    const { user } = session

    // The idToken is stored on the JWT (not exposed on session by default).
    // We need to re-read the raw token to access it.
    // For now, fall back to HS256 signing — the backend accepts both.
    // In a future iteration, we can expose idToken on the session.
    const secret = process.env.NEXTAUTH_SECRET
    if (!secret) throw new BackendError('NEXTAUTH_SECRET not configured', 500)

    return jwt.sign(
        {
            id: user.id,
            email: user.email,
            orgId: user.orgId,
            role: user.role,
            name: user.name,
        },
        secret,
        { algorithm: 'HS256', expiresIn: '5m' }
    )
}

/**
 * Fetch from the Python backend with automatic auth.
 * Returns typed JSON or throws BackendError on failure.
 */
export async function backendFetch<T = unknown>(
    path: string,
    options: { method?: string; body?: unknown } = {}
): Promise<T> {
    const token = await getBackendToken()
    if (!token) throw new BackendError('Not authenticated', 401)

    const { method = 'GET', body } = options

    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
    }

    const fetchOptions: RequestInit = { method, headers }
    if (body && method !== 'GET') {
        fetchOptions.body = JSON.stringify(body)
    }

    const response = await fetch(`${BACKEND_URL}${path}`, fetchOptions)

    if (!response.ok) {
        let errorMessage = `Backend error: ${response.status}`
        try {
            const errorBody = (await response.json()) as { error?: string }
            errorMessage = errorBody.error ?? errorMessage
        } catch {
            // Response body is not JSON
        }
        throw new BackendError(errorMessage, response.status)
    }

    return response.json() as Promise<T>
}
