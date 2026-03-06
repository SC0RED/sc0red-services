import { NextRequest, NextResponse } from 'next/server'
import { backendFetch } from '@/lib/api/serverToken'

export const maxDuration = 300

export async function POST(req: NextRequest) {
    try {
        const body = await req.json()
        const data = await backendFetch('/api/scan/start', { method: 'POST', body })
        return NextResponse.json(data)
    } catch (err: any) {
        const status = err.message?.includes('Not authenticated') ? 401 : 500
        return NextResponse.json({ error: err.message || 'Internal Server Error' }, { status })
    }
}
