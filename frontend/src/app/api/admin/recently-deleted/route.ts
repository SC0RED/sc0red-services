/**
 * Thin proxy to the Python backend's `GET /api/admin/recently-deleted`.
 *
 * Phase 2 of soft-delete recovery: lists tombstoned scans + analyses
 * for the caller's org within a time window (default 30d, max 90d).
 *
 * Auth happens twice — NextAuth wraps the Cognito ID token via
 * `backendFetch`, and the backend handler enforces
 * `authentication.role === 'admin'`. Analysts get a 403 from the
 * backend; the page-level guard hides the link from the sidebar
 * entirely so they shouldn't be able to reach this proxy at all.
 *
 * The `?window=` query param (one of `24h | 7d | 30d | 90d`) is
 * forwarded as-is.
 */

import { NextRequest, NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'
import type { RecentlyDeletedResponse } from '@/lib/types/api'

export async function GET(request: NextRequest) {
    try {
        const window = request.nextUrl.searchParams.get('window')
        const path = window
            ? `/api/admin/recently-deleted?window=${encodeURIComponent(window)}`
            : '/api/admin/recently-deleted'
        const result = await backendFetch<RecentlyDeletedResponse>(path)
        return NextResponse.json(result)
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
