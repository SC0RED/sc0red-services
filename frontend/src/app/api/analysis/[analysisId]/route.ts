import { NextRequest, NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'

export async function GET(_req: NextRequest, { params }: { params: { analysisId: string } }) {
    try {
        const data = await backendFetch(`/api/analysis/${params.analysisId}`)
        return NextResponse.json(data)
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}

export async function DELETE(_req: NextRequest, { params }: { params: { analysisId: string } }) {
    try {
        const data = await backendFetch(`/api/analysis/${params.analysisId}`, { method: 'DELETE' })
        return NextResponse.json(data)
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
