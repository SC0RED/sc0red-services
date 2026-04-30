import type { Metadata } from 'next'

import { BackendError } from '@/lib/api/errors'
import { BACKEND_URL } from '@/lib/config'
import { readSigningSecret, verifyToken } from '@/lib/pdf/token'
import type { AnalysisData } from '@/lib/types/api'

import PrintReport from './PrintReport'

const INTERNAL_API_KEY_ENV = 'INTERNAL_API_KEY'

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
    const internalKey = process.env[INTERNAL_API_KEY_ENV]
    if (!internalKey) {
        throw new Error(`${INTERNAL_API_KEY_ENV} is not set on the print route runtime`)
    }
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
    let secret: string
    try {
        secret = readSigningSecret()
    } catch (error) {
        // Misconfiguration — the env var isn't set. Surface as 500 rather
        // than a misleading 401 so ops sees the real problem.
        throw error
    }

    const verification = verifyToken(token, params.analysisId, secret)
    if (!verification.ok) {
        // Returning JSX with a 401-shaped message is intentional: Next.js
        // server components don't have a clean Response.status path. The
        // caller (the PDF Lambda) treats any non-render output as failure;
        // for a developer hitting this URL by accident the page is plainly
        // labelled "Unauthorized" with the underlying reason.
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

    return <PrintReport analysis={analysis} />
}

function UnauthorizedView({ reason }: { reason: string }) {
    return (
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
    )
}
