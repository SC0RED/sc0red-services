/**
 * Thin proxy to the Python backend's `POST /api/admin/restore`.
 *
 * Phase 2 of soft-delete recovery: restores tombstoned records by
 * clearing `deleted_at` and `ttl`. Body shape: `{ ids: string[] }`,
 * mixed scans + analyses — the backend infers each id's type. Org
 * isolation + admin-role check are enforced server-side.
 *
 * Response: `{ restored: string[], failed: {id, reason}[] }`.
 */

import { NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'
import type { RestoreResponse } from '@/lib/types/api'

export async function POST(request: Request) {
    try {
        const body = (await request.json()) as { ids?: unknown }
        const result = await backendFetch<RestoreResponse>('/api/admin/restore', {
            method: 'POST',
            body,
        })
        return NextResponse.json(result)
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
