import { NextRequest, NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'

export async function POST(_req: NextRequest, { params }: { params: { analysisId: string } }) {
    try {
        const data = await backendFetch(`/api/analysis/${params.analysisId}/reanalyze`, {
            method: 'POST',
            body: {},
        })
        return NextResponse.json(data, { status: 202 })
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
