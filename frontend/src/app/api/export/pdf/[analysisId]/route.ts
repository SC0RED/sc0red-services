import { NextRequest, NextResponse } from 'next/server'

import { emitFromServer } from '@/lib/analytics/emitEvent.server'
import { BackendError } from '@/lib/api/errors'
import { backendFetch, getBackendToken } from '@/lib/api/serverToken'
import { BACKEND_URL } from '@/lib/config'
import { buildContentDisposition, buildPdfFilename } from '@/lib/pdf/filename'
import { readSigningSecret, signToken } from '@/lib/pdf/token'
import type { AnalysisData } from '@/lib/types/api'

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
    // Prefer the explicit env var (set per-environment in CDK so the
    // Lambda's headless browser hits the right Amplify URL). Fall back
    // to the request's origin so a developer running `npm run dev` can
    // exercise the path locally without env tweaks.
    const explicit = process.env.FRONTEND_BASE_URL
    if (explicit) return explicit.replace(/\/$/, '')
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
