import { NextRequest, NextResponse } from 'next/server'
import { backendFetch } from '@/lib/api/serverToken'

export async function GET(
    req: NextRequest,
    { params }: { params: { analysisId: string } }
) {
    try {
        const data = await backendFetch(`/api/analysis/${params.analysisId}`)
        return NextResponse.json(data)
    } catch (err: any) {
        const status = err.message?.includes('Not found') ? 404
            : err.message?.includes('Not authenticated') ? 401 : 500
        return NextResponse.json({ error: err.message || 'Internal Server Error' }, { status })
    }
}

export async function DELETE(
    req: NextRequest,
    { params }: { params: { analysisId: string } }
) {
    try {
        const data = await backendFetch(`/api/analysis/${params.analysisId}`, { method: 'DELETE' })
        return NextResponse.json(data)
    } catch (err: any) {
        const status = err.message?.includes('Not found') ? 404
            : err.message?.includes('Not authenticated') ? 401 : 500
        return NextResponse.json({ error: err.message || 'Internal Server Error' }, { status })
    }
}
