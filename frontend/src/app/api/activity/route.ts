/**
 * Thin proxy to the Python backend's `/api/activity` endpoint.
 *
 * The backend handler projects org-level events from existing DynamoDB
 * records (scan starts, analysis completions, member invites/joins).
 * This proxy carries the NextAuth-managed Cognito ID token via
 * `backendFetch()` and relays the JSON response unchanged.
 *
 * No request body, no query params for v1 — the backend caps the
 * response at 100 events. When pagination becomes necessary, this
 * route should forward the `cursor` query param to the backend.
 */

import { NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'
import type { ActivityEventsResponse } from '@/lib/types/api'

export async function GET() {
    try {
        const result = await backendFetch<ActivityEventsResponse>('/api/activity')
        return NextResponse.json(result)
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
