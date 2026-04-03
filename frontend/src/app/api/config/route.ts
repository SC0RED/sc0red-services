import { NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'

export async function GET() {
    try {
        const data = await backendFetch('/api/config')
        return NextResponse.json(data)
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
