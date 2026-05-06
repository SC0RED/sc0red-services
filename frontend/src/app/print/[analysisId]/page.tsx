import type { Metadata } from 'next'

import { BackendError } from '@/lib/api/errors'
import { BACKEND_URL } from '@/lib/config'
import { readInternalApiKey, readSigningSecret } from '@/lib/pdf/secretSource'
import { verifyToken } from '@/lib/pdf/token'
import type { AnalysisData } from '@/lib/types/api'

import PrintReport from './PrintReport'

/**
 * Print-optimised view of an analysis. Headless Chromium running in the PDF
 * render Lambda navigates here with `?t={signedToken}` and snapshots the
 * page via `page.pdf()`. Token-only auth: no NextAuth session is needed
 * because the URL's HMAC token IS the authorisation. `next.config` and the
 * top-level middleware deliberately do not put `/print/*` behind the
 * authenticated matcher (see `src/middleware.ts`).
 *
 * NOTE: this route lives OUTSIDE the `(authenticated)` route group on
 * purpose, so it does NOT inherit the dashboard sidebar / breadcrumbs.
 * The proposal originally specified `(authenticated)/print/...` but that
 * would mean the headless render captures the chrome we want to avoid.
 */

export const metadata: Metadata = {
    robots: { index: false, follow: false },
    title: 'Print Report',
}

interface PrintPageProps {
    params: { analysisId: string }
    searchParams: { t?: string }
}

/**
 * Headless Chromium has no NextAuth cookies, so the print route can't reuse
 * `backendFetch`. Instead we hit the internal-key endpoint
 * `GET /api/internal/analysis/{id}` with the per-environment shared secret
 * + the org id from the verified URL token. The endpoint validates the key
 * (constant-time) + scopes the read by orgId, returning the same payload
 * shape as the user-facing `/api/analysis/{id}`.
 *
 * The shared secret comes from `INTERNAL_API_KEY` (Secrets Manager-managed)
 * and MUST agree with the same env var on the backend Lambda. Failure mode
 * here is fail-fast: if the key is missing the route 500s rather than
 * silently 401-ing on the backend.
 */
async function fetchAnalysisForPrint(analysisId: string, orgId: string): Promise<AnalysisData> {
    const internalKey = readInternalApiKey()
    const response = await fetch(`${BACKEND_URL}/api/internal/analysis/${analysisId}`, {
        method: 'GET',
        headers: {
            'X-Internal-Api-Key': internalKey,
            'X-Org-Id': orgId,
            'Content-Type': 'application/json',
        },
    })
    if (!response.ok) {
        let message = `Backend internal endpoint returned ${response.status}`
        try {
            const body = (await response.json()) as { error?: string }
            if (body.error) message = body.error
        } catch {
            // Response wasn't JSON — keep the generic message.
        }
        throw new BackendError(message, response.status)
    }
    return response.json() as Promise<AnalysisData>
}

export default async function PrintPage({ params, searchParams }: PrintPageProps) {
    const token = searchParams?.t ?? ''
    // `readSigningSecret` throws a clear `PDF_TOKEN_SECRET is not set`
    // error if the env var is missing — let it propagate as a 500 so ops
    // sees the misconfiguration rather than a misleading 401.
    const secret = readSigningSecret()
    const verification = verifyToken(token, params.analysisId, secret)
    if (!verification.ok) {
        return <UnauthorizedView reason={verification.reason} />
    }

    let analysis: AnalysisData
    try {
        analysis = await fetchAnalysisForPrint(params.analysisId, verification.payload.orgId)
    } catch (error) {
        if (error instanceof BackendError && error.status === 404) {
            return <UnauthorizedView reason="not_found" />
        }
        throw error
    }

    return (
        <>
            {/* IMPORTANT: the render Lambda inspects this marker after `page.goto`
                and BEFORE `page.pdf()`. If the meta is missing or has any value
                other than `ok`, the Lambda bails with a 401 instead of producing
                a "successful" PDF of an error page. Failure modes that flow
                through here today: PDF_TOKEN_SECRET drift between the Next.js
                Lambda runtime and the Node.js render Lambda runtime (rotation
                window, env desync). See `backend/lambdas/pdf-render/src/render.ts`
                — `verifyPrintStatus`. */}
            <PrintStatusMarker status="ok" />
            <PrintReport analysis={analysis} generatedDate={formatGeneratedDate()} />
        </>
    )
}

/**
 * Compute the "Generated <date>" string for the PDF cover.
 *
 * Computed server-side (in this RSC) and threaded through to the
 * client component as a prop so server render + client hydration
 * produce the SAME formatted string. Doing it inside `PrintReport`
 * (a `'use client'` module) would re-execute `new Date()` on
 * hydration, opening a midnight-straddle hydration mismatch and a
 * potentially different result if the headless browser locale ever
 * drifts from the server.
 *
 * Locked to `'en-US'` because the printed PDF is an English-only
 * artifact today; if/when localisation lands, this resolves to a
 * deterministic UTC formatter or a per-locale variant threaded
 * through the page params.
 */
function formatGeneratedDate(): string {
    return new Date().toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
    })
}

/**
 * Single source of truth for the meta-marker contract between the print route
 * and the render Lambda. Re-used by `UnauthorizedView` so the failure case
 * also emits a marker (lets the Lambda distinguish "no marker = misrouted /
 * page didn't render" from "marker present = page rendered but auth failed").
 */
const PRINT_STATUS_META = 'x-print-status'
type PrintStatus = 'ok' | 'unauthorized' | 'not_found'

function PrintStatusMarker({ status }: { status: PrintStatus }) {
    return <meta name={PRINT_STATUS_META} content={status} />
}

function UnauthorizedView({ reason }: { reason: string }) {
    const status: PrintStatus = reason === 'not_found' ? 'not_found' : 'unauthorized'
    return (
        <>
            <PrintStatusMarker status={status} />
            <main
                style={{
                    minHeight: '100vh',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.75rem',
                    background: 'var(--bg-base)',
                    color: 'var(--text-primary)',
                    fontFamily: 'var(--font-sans)',
                    padding: '2rem',
                    textAlign: 'center',
                }}
            >
                <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>Unauthorized</h1>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem' }}>
                    This print URL is not valid. Reason: <code>{reason}</code>.
                </p>
                <p style={{ color: 'var(--text-tertiary)', fontSize: '0.875rem' }}>
                    Print URLs expire 60 seconds after they are minted. Re-export from the analysis page.
                </p>
            </main>
        </>
    )
}
