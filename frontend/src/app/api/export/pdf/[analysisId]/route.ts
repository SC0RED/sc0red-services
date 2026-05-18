import { NextRequest, NextResponse } from 'next/server'

import { emitFromServer } from '@/lib/analytics/emitEvent.server'
import { BackendError } from '@/lib/api/errors'
import { backendFetch, getBackendToken } from '@/lib/api/serverToken'
import { BACKEND_URL } from '@/lib/config'
import { buildContentDisposition, buildPdfFilename } from '@/lib/pdf/filename'
import { readSigningSecret } from '@/lib/pdf/secretSource'
import { signToken } from '@/lib/pdf/token'
import type { AnalysisData } from '@/lib/types/api'

/**
 * Async export response shape — matches the Python backend
 * (`backend/src/handlers/pdf_export_handlers.py`).
 *
 *   200 OK   { status: 'ready', url, generatedAt }    — cached path
 *   202      { status: 'rendering', startedAt }       — cold path / dedupe
 *   500      { error, code }                          — server-side failure
 */
interface ExportPostResponse {
    status: 'ready' | 'rendering' | 'failed'
    url?: string
    generatedAt?: string
    startedAt?: string
    error?: string
}

/**
 * Server-side PDF export endpoint.
 *
 *   1. Auth check — Cognito session via NextAuth (raises 401 if absent).
 *   2. Fetch the analysis to derive the filename + opportunity count for
 *      the analytics event. The analysis fetch also serves as the org-
 *      scoping check: backendFetch returns 404 if the user can't see this
 *      analysis, and we propagate that to the caller.
 *   3. Mint a 60-second HMAC URL token scoped to {analysisId, orgId}.
 *   4. Invoke the PDF render endpoint at `${BACKEND_URL}/api/admin/render-pdf`
 *      (mounted on the Node.js Puppeteer Lambda via API Gateway, gated by
 *      the same Cognito JWT). Returns the binary PDF.
 *   5. Stream the PDF back with `Content-Disposition: attachment; …` so the
 *      browser saves it instead of opening it inline.
 *   6. Emit `sc0red_cta_rendered_in_pdf` when the analysis has at least one
 *      opportunity. Matches the prior route's behaviour for funnel parity.
 *
 * Replaces the prior HTML-pretending-to-be-PDF route. The only behavioural
 * change visible to existing analytics is the `Content-Type` flip from
 * `text/html` to `application/pdf`.
 */

const RENDER_TIMEOUT_MS = 30_000
const RENDER_PATH = '/api/admin/render-pdf'

interface RenderRequestBody {
    analysisId: string
    token: string
    frontendBaseUrl: string
    companyName: string
}

function readFrontendBaseUrl(req: NextRequest): string {
    // 1. Prefer the explicit env var (set per-environment in CDK so the
    //    Lambda's headless browser hits the right Amplify URL).
    const explicit = process.env.FRONTEND_BASE_URL
    if (explicit) return explicit.replace(/\/$/, '')

    // 2. Fall back to `X-Forwarded-Host` if the proxy set it. On Amplify
    //    SSR, Next.js binds to `localhost:3000` internally, so
    //    `req.nextUrl.origin` returns the wrong URL. CloudFront sets
    //    `X-Forwarded-Host` + `X-Forwarded-Proto` to the public origin
    //    when forwarding to the Lambda — use those if present.
    const forwardedHost = req.headers.get('x-forwarded-host')
    if (forwardedHost) {
        const forwardedProto = req.headers.get('x-forwarded-proto') ?? 'https'
        return `${forwardedProto}://${forwardedHost}`
    }

    // 3. Last resort: `req.nextUrl.origin` — works for `npm run dev` on
    //    the developer's laptop where the request actually originates
    //    on `localhost:3000`. Should NEVER hit on Amplify SSR if step 1
    //    or 2 fired correctly.
    return req.nextUrl.origin
}

async function invokeRenderLambda(body: RenderRequestBody): Promise<Response> {
    const token = await getBackendToken()
    if (!token) throw new BackendError('Not authenticated', 401)

    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), RENDER_TIMEOUT_MS)
    try {
        return await fetch(`${BACKEND_URL}${RENDER_PATH}`, {
            method: 'POST',
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                Accept: 'application/pdf',
            },
            body: JSON.stringify(body),
            signal: controller.signal,
        })
    } finally {
        clearTimeout(timeout)
    }
}

export async function GET(req: NextRequest, { params }: { params: { analysisId: string } }) {
    try {
        // (1)+(2): Fetch the analysis. backendFetch handles auth + 401 +
        // org scoping; if the analysis isn't visible to the caller we
        // propagate the same 404 the underlying endpoint returns.
        const analysis = await backendFetch<AnalysisData>(`/api/analysis/${params.analysisId}`)
        const orgId = await resolveOrgId()

        // (3): Mint the URL token. The PDF Lambda passes this to the print
        // route via `?t=`; the print route validates HMAC + expiry +
        // analysisId match before rendering.
        const token = signToken({ analysisId: params.analysisId, orgId }, readSigningSecret())

        // (4): Invoke the render Lambda.
        const response = await invokeRenderLambda({
            analysisId: params.analysisId,
            token,
            frontendBaseUrl: readFrontendBaseUrl(req),
            companyName: analysis.companyName,
        })

        if (!response.ok) {
            // LOW-priority review nit: the rest of the API returns
            // `{error, code}` JSON. This route returns plain text because
            // the frontend caller (`ExportPDFButton`) never displays the
            // body — it shows `"PDF export failed (HTTP ${status})"` from
            // the response code alone. Migrating to JSON here would
            // change zero observable behaviour today; deferred until a
            // future caller surfaces the body.
            const message = `PDF render failed (HTTP ${response.status})`
            return new NextResponse(message, { status: response.status })
        }

        const pdfBuffer = await response.arrayBuffer()

        // (6): Fire the analytics event AFTER the render succeeded — we
        // only count "actually delivered" PDFs, not requests-that-erred.
        // Matches the prior route's gating: opportunities-zero analyses
        // do NOT emit (avoids polluting funnel queries).
        const opportunities = analysis.opportunities ?? []
        if (opportunities.length > 0) {
            void emitFromServer('sc0red_cta_rendered_in_pdf', {
                analysisId: params.analysisId,
                opportunityCount: opportunities.length,
            })
        }

        // (5): Return the PDF with the user-facing filename.
        const filename = buildPdfFilename(analysis.companyName, analysis.analyzedAt)
        return new NextResponse(pdfBuffer, {
            status: 200,
            headers: {
                'Content-Type': 'application/pdf',
                'Content-Disposition': buildContentDisposition(filename),
                'Cache-Control': 'no-store',
            },
        })
    } catch (error: unknown) {
        const status = error instanceof BackendError ? error.status : 500
        const message = error instanceof Error ? error.message : 'PDF export failed'
        return new NextResponse(message, { status })
    }
}

/**
 * POST — primary entry point for the async PDF export flow.
 *
 * Thin proxy to the Python backend's
 * ``POST /api/export/pdf/<analysisId>``. The backend handles auth +
 * org-scoping + cache lookup + Lambda async-invoke; we forward the
 * response shape verbatim:
 *
 *   200 OK   { status: 'ready',     url, generatedAt }   — cached
 *   202      { status: 'rendering', startedAt }          — cold / dedupe
 *   500      { status: 'failed',    error }              — sync failure
 *
 * The frontend ``ExportPDFButton`` either redirects to ``url`` (cached
 * path) or starts polling the sibling ``/status`` route (cold path).
 *
 * Analytics: emits ``sc0red_cta_rendered_in_pdf`` on the cached path
 * (we know the PDF was rendered, it's just being re-served from
 * cache). Cold-path emission is deferred to Phase 4 — we'd need a
 * separate "PDF delivered" signal because POST time precedes the
 * actual render. The funnel loses cold-path exports during the brief
 * Phase 3 → Phase 4 window, which is an acceptable trade-off for the
 * simpler implementation here.
 *
 * Funnel-gating preserved from legacy: only emit when the analysis
 * has at least one opportunity (zero-opp analyses don't have CTAs
 * to render, so they'd pollute the "CTA-in-PDF" funnel).
 *
 * See ``openspec/changes/async-pdf-export-with-cache/`` for the design.
 */
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
            // We fetch the analysis here (one extra GET) to read
            // ``opportunities.length`` for the funnel gate that matches
            // the legacy GET handler's behaviour. The fetch is cheap
            // (DDB GetItem, ~10 ms warm) and runs in parallel with the
            // response from the user's perspective (the browser's
            // redirect to the presigned URL is independent of this).
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
                // Analytics is best-effort. A failure to fetch the
                // analysis MUST NOT block the user's download.
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

/**
 * Pulls the user's `orgId` claim from the NextAuth JWT. Done as a separate
 * helper because the `getBackendToken` path returns the raw idToken we
 * forward to the backend, while this returns the JWT payload's org_id.
 */
async function resolveOrgId(): Promise<string> {
    // The user's session-level `orgId` is on the NextAuth JWT under the
    // standard NextAuth/JWT layout. We import here (not at module top)
    // so the test of `signToken` doesn't require a session mock.
    const { getToken } = await import('next-auth/jwt')
    const { cookies, headers } = await import('next/headers')

    const cookieStore = await cookies()
    const headerStore = await headers()
    const token = await getToken({
        req: {
            cookies: Object.fromEntries(cookieStore.getAll().map((c) => [c.name, c.value])),
            headers: Object.fromEntries(headerStore.entries()),
        } as never,
        secret: process.env.NEXTAUTH_SECRET,
    })
    const orgId = (token as { orgId?: string } | null)?.orgId
    if (!orgId) throw new BackendError('Session missing org id', 401)
    return orgId
}
