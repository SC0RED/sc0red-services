import { NextRequest, NextResponse } from 'next/server'

import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'

export async function GET(_req: NextRequest, { params }: { params: { analysisId: string } }) {
    try {
        const data = await backendFetch(`/api/analysis/${params.analysisId}`)
        return NextResponse.json(data)
    } catch (error: unknown) {
        const status = error instanceof BackendError ? error.status : 500
        const message = error instanceof Error ? error.message : 'Internal Server Error'
        return NextResponse.json({ error: message }, { status })
    }
}

export async function DELETE(_req: NextRequest, { params }: { params: { analysisId: string } }) {
    try {
        const data = await backendFetch(`/api/analysis/${params.analysisId}`, { method: 'DELETE' })
        return NextResponse.json(data)
    } catch (error: unknown) {
        const status = error instanceof BackendError ? error.status : 500
        const message = error instanceof Error ? error.message : 'Internal Server Error'
        return NextResponse.json({ error: message }, { status })
    }
}
