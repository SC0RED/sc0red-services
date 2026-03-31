/**
 * Server-side backend token utility.
 *
 * Extracts the Cognito ID token from the NextAuth session and passes it
 * directly to the Python backend. The backend validates the RS256 JWT
 * against the Cognito JWKS endpoint.
 */

import { getServerSession } from 'next-auth'

import { BackendError } from '@/lib/api/errors'
import { authOptions } from '@/lib/auth/authOptions'
import { BACKEND_URL } from '@/lib/config'

/**
 * Get the Cognito ID token from the current session.
 */
export async function getBackendToken(): Promise<string | null> {
    const session = await getServerSession(authOptions)
    if (!session?.user?.idToken) return null
    return session.user.idToken
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
