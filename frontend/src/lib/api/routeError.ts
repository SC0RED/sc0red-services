import { NextResponse } from 'next/server'

import { BackendError } from './errors'

export function handleRouteError(error: unknown): NextResponse {
    const status = error instanceof BackendError ? error.status : 500
    const message = error instanceof Error ? error.message : 'Internal Server Error'
    return NextResponse.json({ error: message }, { status })
}
