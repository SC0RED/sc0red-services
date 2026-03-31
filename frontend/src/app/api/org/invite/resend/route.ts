import { NextRequest, NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'

export async function POST(request: NextRequest) {
    try {
        const body = await request.json()
        const data = await backendFetch('/api/org/invite/resend', { method: 'POST', body })
        return NextResponse.json(data)
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
