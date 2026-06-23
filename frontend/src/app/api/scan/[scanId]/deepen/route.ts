import { NextRequest, NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'

export const maxDuration = 300

export async function POST(_req: NextRequest, { params }: { params: { scanId: string } }) {
    try {
        const data = await backendFetch(`/api/scan/${params.scanId}/deepen`, { method: 'POST' })
        return NextResponse.json(data)
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
