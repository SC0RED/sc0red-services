import { NextRequest, NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'

export async function POST(req: NextRequest, { params }: { params: { analysisId: string } }) {
    try {
        const body = (await req.json()) as unknown
        const data = await backendFetch(`/api/analysis/${params.analysisId}/documents`, {
            method: 'POST',
            body,
        })
        return NextResponse.json(data, { status: 201 })
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
