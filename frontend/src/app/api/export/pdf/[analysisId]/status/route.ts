import { NextResponse } from 'next/server'

import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'

/**
 * Status response shape — matches the Python backend
 * (``handle_get_export_status`` in ``pdf_export_handlers.py``).
 *
 *   { status: 'none' }                                  — no record yet
 *   { status: 'rendering', startedAt }                  — in flight
 *   { status: 'ready', url, generatedAt }               — done, presigned URL
 *   { status: 'failed', error }                         — fatal or stale-as-failed
 *
 * The frontend polls this at 2-second intervals (then 5s after 10 polls)
 * while the ``ExportPDFButton`` is in its "Generating PDF…" state. The
 * backend folds stale-rendering (>60 s old) into a synthetic ``failed``
 * without mutating the persisted record — the next POST re-triggers a
 * fresh render naturally. See
 * ``openspec/changes/async-pdf-export-with-cache/``.
 */
interface ExportStatusResponse {
    status: 'none' | 'rendering' | 'ready' | 'failed'
    url?: string
    generatedAt?: string
    startedAt?: string
    error?: string
}

export async function GET(_req: Request, { params }: { params: { analysisId: string } }) {
    try {
        const result = await backendFetch<ExportStatusResponse>(`/api/export/pdf/${params.analysisId}/status`)
        return NextResponse.json(result)
    } catch (error: unknown) {
        const status = error instanceof BackendError ? error.status : 500
        const message = error instanceof Error ? error.message : 'PDF status check failed'
        return NextResponse.json({ error: message }, { status })
    }
}
