import { NextRequest, NextResponse } from 'next/server'
import { backendFetch } from '@/lib/api/serverToken'

export async function GET(
    req: NextRequest,
    { params }: { params: { scanId: string } }
) {
    try {
        const data = await backendFetch(`/api/scan/${params.scanId}`)
        return NextResponse.json(data)
    } catch (err: any) {
        const status = err.message?.includes('Not authenticated') ? 401 : 500
        return NextResponse.json({ error: err.message || 'Internal Server Error' }, { status })
    }
}
