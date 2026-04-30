import type { Metadata } from 'next'

import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'
import { readSigningSecret, verifyToken } from '@/lib/pdf/token'
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
 * `backendFetch` reuses the caller's NextAuth session token. That works for
 * a developer hitting `/print/{id}?t=...` in their own browser, but the PDF
 * render Lambda's headless Chromium has no cookies — so the production path
 * needs a service-account or internal-key auth approach. That's wired up in
 * §3 of the polished-pdf-export change. For now the route is functionally
 * complete for browser-based smoke testing; the Lambda integration will
 * extend the data-fetch helper in a follow-up commit.
 */
async function fetchAnalysisForPrint(analysisId: string): Promise<AnalysisData> {
    return backendFetch<AnalysisData>(`/api/analysis/${analysisId}`)
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
        analysis = await fetchAnalysisForPrint(params.analysisId)
    } catch (error) {
        if (error instanceof BackendError && error.status === 404) {
            return <UnauthorizedView reason="not_found" />
        }
        throw error
    }

    // Defensive cross-check: the backend should already have rejected a
    // mismatched org via its own auth, but if a token was issued for org A
    // and somehow reaches a session for org B, refuse to render.
    // (Once the Lambda flow lands and uses internal auth, this is the only
    // boundary that catches an org mismatch.)
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
