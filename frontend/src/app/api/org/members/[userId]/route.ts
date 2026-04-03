import { NextRequest, NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'

export async function DELETE(_req: NextRequest, { params }: { params: { userId: string } }) {
    try {
        const data = await backendFetch(`/api/org/members/${params.userId}`, { method: 'DELETE' })
        return NextResponse.json(data)
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
