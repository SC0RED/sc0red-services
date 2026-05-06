import { NextRequest, NextResponse } from 'next/server'

import { handleRouteError } from '@/lib/api/routeError'
import { backendFetch } from '@/lib/api/serverToken'

/**
 * Thin proxy for the on-demand strategy-map trigger
 * (`strategy-map-on-demand` Phase B). Forwards the authenticated POST
 * to the Python backend's `handle_generate_strategy_map`, which enqueues
 * a worker job on the dedicated SQS queue and returns 202.
 *
 * Backend success contract: `202 { status: "queued", analysisId: "..." }`.
 * Backend non-success cases (404, 409 already-running, 503 feature-disabled)
 * surface here as a `BackendError` and are mapped through
 * `handleRouteError` to preserve the upstream status + message — the
 * `StrategyMapCTA` component renders the message inline.
 */
export async function POST(_req: NextRequest, { params }: { params: { analysisId: string } }) {
    try {
        const data = await backendFetch(`/api/analysis/${params.analysisId}/strategy-map`, {
            method: 'POST',
            body: {},
        })
        return NextResponse.json(data, { status: 202 })
    } catch (error: unknown) {
        return handleRouteError(error)
    }
}
