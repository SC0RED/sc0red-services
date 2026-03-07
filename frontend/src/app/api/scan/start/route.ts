import { NextRequest, NextResponse } from 'next/server'

import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'

export const maxDuration = 300

export async function POST(req: NextRequest) {
    try {
        const body = (await req.json()) as unknown
        const data = await backendFetch('/api/scan/start', { method: 'POST', body })
        return NextResponse.json(data)
    } catch (error: unknown) {
        const status = error instanceof BackendError ? error.status : 500
        const message = error instanceof Error ? error.message : 'Internal Server Error'
        return NextResponse.json({ error: message }, { status })
    }
}
