import { NextRequest, NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'

export const maxDuration = 300

export async function POST(req: NextRequest, { params }: { params: { scanId: string } }) {
    try {
        const body = (await req.json()) as unknown
        const data = await backendFetch(`/api/scan/${params.scanId}/confirm`, { method: 'POST', body })
        return NextResponse.json(data)
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
