import { NextRequest, NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'

export async function POST(request: NextRequest) {
    try {
        const body = await request.json()
        const data = await backendFetch('/api/org/invite', { method: 'POST', body })
        return NextResponse.json(data, { status: 201 })
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
