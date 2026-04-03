import { getToken } from 'next-auth/jwt'
import { NextResponse, type NextRequest } from 'next/server'

function isTokenExpired(idToken: string): boolean {
    try {
        const payload = JSON.parse(Buffer.from(idToken.split('.')[1], 'base64url').toString())
        return Date.now() > payload.exp * 1000
    } catch {
        return true
    }
}

export async function middleware(request: NextRequest) {
    const token = await getToken({
        req: request,
        secret: process.env.NEXTAUTH_SECRET,
    })

    const isAuthenticated = token?.idToken && !isTokenExpired(token.idToken as string)

    if (!isAuthenticated) {
        // API routes: return 401 JSON (client handles signOut)
        if (request.nextUrl.pathname.startsWith('/api/')) {
            return NextResponse.json({ error: 'Session expired' }, { status: 401 })
        }
        // Pages: redirect to login
        return NextResponse.redirect(new URL('/login', request.url))
    }

    return NextResponse.next()
}

export const config = {
    matcher: [
        '/dashboard/:path*',
        '/scan/:path*',
        '/analysis/:path*',
        '/portfolio/:path*',
        '/analyses/:path*',
        '/team/:path*',
        '/api/scan/:path*',
        '/api/analysis/:path*',
        '/api/org/:path*',
        '/api/config/:path*',
        '/api/export/:path*',
    ],
}
