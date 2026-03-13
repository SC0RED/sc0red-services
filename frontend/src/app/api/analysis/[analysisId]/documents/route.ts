import { NextRequest, NextResponse } from 'next/server'

import { BackendError } from '@/lib/api/errors'
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
        const status = error instanceof BackendError ? error.status : 500
        const message = error instanceof Error ? error.message : 'Internal Server Error'
        return NextResponse.json({ error: message }, { status })
    }
}
