import { NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { BACKEND_URL } from '@/lib/config'

export async function GET() {
    try {
        const response = await fetch(`${BACKEND_URL}/api/config`)
        const data = (await response.json()) as unknown
        return NextResponse.json(data)
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
