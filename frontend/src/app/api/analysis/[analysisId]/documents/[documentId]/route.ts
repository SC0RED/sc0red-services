import { NextRequest, NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'

export async function DELETE(
    _req: NextRequest,
    { params }: { params: { analysisId: string; documentId: string } }
) {
    try {
        const data = await backendFetch(`/api/analysis/${params.analysisId}/documents/${params.documentId}`, {
            method: 'DELETE',
        })
        return NextResponse.json(data)
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
