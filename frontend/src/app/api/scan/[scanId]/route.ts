import { NextRequest, NextResponse } from 'next/server'

import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'

export async function GET(_req: NextRequest, { params }: { params: { scanId: string } }) {
    try {
        const data = await backendFetch(`/api/scan/${params.scanId}`)
        const { status, progress, analyses } = data as {
            status?: string
            progress?: number
            analyses?: unknown[]
        }
        // eslint-disable-next-line no-console
        console.log(
            `[poll] scan=${params.scanId} status=${status} progress=${progress} analyses=${analyses?.length ?? 0}`
        )
        return NextResponse.json(data)
    } catch (error: unknown) {
        const status = error instanceof BackendError ? error.status : 500
        const message = error instanceof Error ? error.message : 'Internal Server Error'
        // eslint-disable-next-line no-console
        console.error(`[poll] scan=${params.scanId} error=${message} status=${status}`)
        return NextResponse.json({ error: message }, { status })
    }
}
