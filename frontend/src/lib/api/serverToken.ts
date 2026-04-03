/**
 * Server-side backend token utility.
 *
 * Extracts the Cognito ID token from the NextAuth JWT (server-side only)
 * and passes it to the Python backend for RS256 validation.
 */

import { getToken } from 'next-auth/jwt'
import { cookies, headers } from 'next/headers'
import { redirect } from 'next/navigation'

import { BackendError } from '@/lib/api/errors'
import { BACKEND_URL } from '@/lib/config'

/**
 * Get the Cognito ID token from the NextAuth JWT.
 * Uses getToken() which reads the raw JWT — idToken is stored there
 * but NOT exposed on the client-facing session.
 */
export async function getBackendToken(): Promise<string | null> {
    // getToken() needs the request cookies — use next/headers
    const cookieStore = await cookies()
    const headerStore = await headers()
    const token = await getToken({
        req: {
            cookies: Object.fromEntries(cookieStore.getAll().map((c) => [c.name, c.value])),
            headers: Object.fromEntries(headerStore.entries()),
        } as never,
        secret: process.env.NEXTAUTH_SECRET,
    })

    return token?.idToken as string | null
}

/**
 * Clear the NextAuth session cookie and redirect to login.
 * Used when the Cognito token inside the session has expired —
 * the NextAuth session is still valid but the backend rejects it.
 * We must delete the cookie first to prevent a redirect loop
 * (middleware sees valid session → redirects back to dashboard).
 */
async function clearSessionAndRedirect(): Promise<never> {
    const cookieStore = await cookies()
    const sessionCookieNames = cookieStore
        .getAll()
        .filter((c) => c.name.includes('next-auth'))
        .map((c) => c.name)

    for (const name of sessionCookieNames) {
        cookieStore.delete(name)
    }

    redirect('/login')
}

/**
 * Fetch from the Python backend with automatic auth.
 * Returns typed JSON or throws BackendError on failure.
 * Redirects to login (with session cleared) on 401/missing token.
 */
export async function backendFetch<T = unknown>(
    path: string,
    options: { method?: string; body?: unknown } = {}
): Promise<T> {
    const token = await getBackendToken()
    if (!token) await clearSessionAndRedirect()

    const { method = 'GET', body } = options

    const fetchHeaders: Record<string, string> = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
    }

    const fetchOptions: RequestInit = { method, headers: fetchHeaders }
    if (body && method !== 'GET') {
        fetchOptions.body = JSON.stringify(body)
    }

    const response = await fetch(`${BACKEND_URL}${path}`, fetchOptions)

    if (response.status === 401) {
        await clearSessionAndRedirect()
    }

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
