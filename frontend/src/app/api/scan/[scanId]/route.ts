import { NextRequest, NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'

export async function GET(_req: NextRequest, { params }: { params: { scanId: string } }) {
    try {
        const data = await backendFetch(`/api/scan/${params.scanId}`)
        const { status, progress, analyses } = data as {
            status?: string
            progress?: number
            analyses?: unknown[]
        }
        // eslint-disable-next-line no-console
        console.log(
            `[poll] scan=${params.scanId} status=${status} progress=${progress} analyses=${analyses?.length ?? 0}`
        )
        return NextResponse.json(data)
    } catch (error: unknown) {
        // eslint-disable-next-line no-console
        console.error(
            `[poll] scan=${params.scanId} error=${error instanceof Error ? error.message : 'unknown'}`
        )
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
