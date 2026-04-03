import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'

/**
 * Clears NextAuth session cookies and redirects to /login.
 *
 * Used when the Cognito ID token inside the NextAuth session has expired.
 * Cookies can only be modified in Route Handlers, not Server Components —
 * so backendFetch() redirects here on 401 instead of deleting cookies directly.
 */
export async function GET() {
    const cookieStore = await cookies()
    const sessionCookies = cookieStore.getAll().filter((c) => c.name.includes('next-auth'))

    for (const cookie of sessionCookies) {
        cookieStore.delete(cookie.name)
    }

    return NextResponse.redirect(new URL('/login', process.env.NEXTAUTH_URL || 'http://localhost:3000'))
}
