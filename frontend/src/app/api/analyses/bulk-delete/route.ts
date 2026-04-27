/**
 * Thin proxy to the Python backend's `POST /api/analyses/bulk-delete`.
 *
 * The backend handler deletes every supplied analysis id, then makes
 * the cascade-to-scan decision in a single post-delete pass — this is
 * the race-immunity property that the bulk endpoint exists to provide.
 * See `backend/src/handlers/analysis_handlers.py:handle_bulk_delete_analyses`.
 *
 * Like every other route in this app, the proxy carries the
 * NextAuth-managed Cognito ID token via `backendFetch()` and relays the
 * JSON response unchanged.
 */

import { NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'

interface BulkDeleteResponse {
    deleted: string[]
    failed: { id: string; reason: string }[]
    deletedScans: string[]
}

export async function POST(request: Request) {
    try {
        const body = (await request.json()) as { ids?: unknown }
        const result = await backendFetch<BulkDeleteResponse>('/api/analyses/bulk-delete', {
            method: 'POST',
            body,
        })
        return NextResponse.json(result)
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
