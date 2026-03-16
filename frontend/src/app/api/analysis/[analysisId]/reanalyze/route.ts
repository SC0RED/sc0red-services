import { NextRequest, NextResponse } from 'next/server'

import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'

export async function POST(_req: NextRequest, { params }: { params: { analysisId: string } }) {
    try {
        const data = await backendFetch(`/api/analysis/${params.analysisId}/reanalyze`, {
            method: 'POST',
            body: {},
        })
        return NextResponse.json(data, { status: 202 })
    } catch (error: unknown) {
        const status = error instanceof BackendError ? error.status : 500
        const message = error instanceof Error ? error.message : 'Internal Server Error'
        return NextResponse.json({ error: message }, { status })
    }
}
