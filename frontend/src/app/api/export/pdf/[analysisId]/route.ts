import { NextRequest, NextResponse } from 'next/server'

import { emitFromServer } from '@/lib/analytics/emitEvent.server'
import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'
import type { AnalysisData } from '@/lib/types/api'

/**
 * Async PDF export — primary entry point.
 *
 * Thin proxy to the Python backend's ``POST /api/export/pdf/<analysisId>``.
 * Backend handles auth + org-scoping + cache lookup + Lambda async-invoke;
 * we forward the response shape verbatim:
 *
 *   200 OK   { status: 'ready',     url, generatedAt }   — cached
 *   202      { status: 'rendering', startedAt }          — cold / dedupe
 *   500      { status: 'failed',    error }              — sync failure
 *
 * The frontend ``ExportPDFButton`` either redirects to ``url`` (cached
 * path) or polls the sibling ``/status`` route (cold path).
 *
 * Analytics: emits ``sc0red_cta_rendered_in_pdf`` on the cached path —
 * we know the PDF was rendered, it's just being re-served from cache.
 * Cold-path emission would need a "delivered" signal that POST time
 * can't provide; the cold path falls outside this funnel metric. The
 * gate (``opportunities.length > 0``) is preserved from the legacy
 * sync handler — zero-opp analyses don't have CTAs to render.
 *
 * History: the legacy synchronous ``GET`` handler (Cognito + token
 * minting + boto3 invoke + binary PDF response) was retired in Phase 4
 * of ``async-pdf-export-with-cache``. The token-minting and direct
 * Lambda invoke now live entirely server-side in the Python backend
 * (``backend/src/handlers/pdf_export_handlers.py``).
 */
interface ExportPostResponse {
    status: 'ready' | 'rendering' | 'failed'
    url?: string
    generatedAt?: string
    startedAt?: string
    error?: string
}

export async function POST(_req: NextRequest, { params }: { params: { analysisId: string } }) {
    try {
        const result = await backendFetch<ExportPostResponse>(`/api/export/pdf/${params.analysisId}`, {
            method: 'POST',
            body: {},
        })

        if (result.status === 'failed') {
            // Synchronous failure (rare: missing config, async-invoke
            // throttled). Return 5xx so access logs / monitoring reflect
            // the failure — the frontend reads ``body.status`` anyway.
            return NextResponse.json(result, { status: 500 })
        }

        if (result.status === 'ready') {
            // Cached path — fire the analytics event before responding.
            // The extra analysis fetch is cheap (DDB GetItem, ~10 ms
            // warm) and best-effort: a failure MUST NOT block the
            // user's download.
            try {
                const analysis = await backendFetch<AnalysisData>(`/api/analysis/${params.analysisId}`)
                const opportunities = analysis.opportunities ?? []
                if (opportunities.length > 0) {
                    void emitFromServer('sc0red_cta_rendered_in_pdf', {
                        analysisId: params.analysisId,
                        opportunityCount: opportunities.length,
                    })
                }
            } catch {
                // Analytics is best-effort.
            }
            return NextResponse.json(result, { status: 200 })
        }

        // status === 'rendering'
        return NextResponse.json(result, { status: 202 })
    } catch (error: unknown) {
        const status = error instanceof BackendError ? error.status : 500
        const message = error instanceof Error ? error.message : 'PDF export failed'
        return NextResponse.json({ error: message }, { status })
    }
}
