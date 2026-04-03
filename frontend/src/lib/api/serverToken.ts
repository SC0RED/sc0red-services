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
 * Fetch from the Python backend with automatic auth.
 * Returns typed JSON or throws BackendError on failure.
 */
export async function backendFetch<T = unknown>(
    path: string,
    options: { method?: string; body?: unknown } = {}
): Promise<T> {
    const token = await getBackendToken()
    if (!token) redirect('/login')

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
        redirect('/login')
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
