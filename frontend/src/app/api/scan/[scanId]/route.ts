import { NextRequest, NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'

export async function GET(_req: NextRequest, { params }: { params: { scanId: string } }) {
    try {
        const data = await backendFetch(`/api/scan/${params.scanId}`)
        return NextResponse.json(data)
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}

export async function DELETE(_req: NextRequest, { params }: { params: { scanId: string } }) {
    try {
        const data = await backendFetch(`/api/scan/${params.scanId}`, { method: 'DELETE' })
        return NextResponse.json(data)
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
