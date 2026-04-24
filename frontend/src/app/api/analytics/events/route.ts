/**
 * Thin proxy to the Python backend's `/api/analytics/events` endpoint.
 *
 * Mirrors the pattern used by every other Next.js API route in this app:
 * pull the Cognito ID token out of the NextAuth JWT via `backendFetch()`,
 * forward the body, and relay the backend's status code. We deliberately
 * do NOT validate the envelope on the Next.js side — the backend is the
 * authoritative validator and returns a structured 400, which we pass
 * through so client-side error logging stays actionable.
 */

import { NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'

export async function POST(request: Request) {
    try {
        const body = (await request.json()) as unknown
        const result = await backendFetch<{ accepted: boolean }>('/api/analytics/events', {
            method: 'POST',
            body,
        })
        return NextResponse.json(result, { status: 202 })
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
