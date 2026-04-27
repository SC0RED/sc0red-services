/**
 * Client-side analytics emit helper.
 *
 * Posts CTA interaction events to the Next.js proxy route
 * (`/api/analytics/events`), which in turn forwards to the Python backend
 * with the user's Cognito ID token attached. Design decisions:
 *
 * - **`event_id` and `timestamp` are generated here** so replays and
 *   duplicate-delivery can be deduped downstream in Logs Insights.
 * - **Failures are swallowed**. CTA analytics are observability, not
 *   user-facing — a failed emit must NEVER block a banner expand or a
 *   link click. Errors log to the console in development only.
 * - **Fire-and-forget**. Callers should invoke with `void emit(...)`.
 *   The fetch uses `keepalive: true` so the request survives even if
 *   the current page starts unloading (e.g., a same-tab navigation)
 *   before the response arrives.
 */

import {
    ANALYTICS_VERSION,
    type ActiveLeverFilter,
    type AnalyticsEvent,
    type PdfEventContext,
    type WebAnalyticsEventType,
    type WebEventContext,
} from '@/lib/types/analytics'

const ENDPOINT = '/api/analytics/events'

function generateEventId(): string {
    // crypto.randomUUID is available in all modern browsers + Node 19+.
    // Fallback to Math.random just so we never crash in a misconfigured
    // environment — collisions are acceptable here.
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
        return crypto.randomUUID()
    }
    return `ev-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function buildWebEnvelope(eventType: WebAnalyticsEventType, context: WebEventContext): AnalyticsEvent {
    return {
        event_id: generateEventId(),
        event_type: eventType,
        timestamp: new Date().toISOString(),
        analytics_version: ANALYTICS_VERSION,
        source: 'web',
        analysis_id: context.analysisId,
        opportunity_count: context.opportunityCount,
        active_lever_filter: context.activeLeverFilter,
    }
}

export function buildPdfEnvelope(context: PdfEventContext): AnalyticsEvent {
    return {
        event_id: generateEventId(),
        event_type: 'sc0red_cta_rendered_in_pdf',
        timestamp: new Date().toISOString(),
        analytics_version: ANALYTICS_VERSION,
        source: 'pdf',
        analysis_id: context.analysisId,
        opportunity_count: context.opportunityCount,
        active_lever_filter: null,
    }
}

/**
 * Emit a web-surface CTA analytics event. Never throws.
 *
 * Returns a Promise for test ergonomics, but production callers should
 * treat it as fire-and-forget (`void emit(...)`): React does not suspend
 * an element's default action (e.g., anchor navigation) for an async
 * handler, so awaiting will not delay navigation. Durability relies on
 * `keepalive: true` in the underlying fetch.
 */
export async function emit(eventType: WebAnalyticsEventType, context: WebEventContext): Promise<void> {
    const envelope = buildWebEnvelope(eventType, context)
    await postEnvelope(envelope)
}

async function postEnvelope(envelope: AnalyticsEvent): Promise<void> {
    try {
        const response = await fetch(ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(envelope),
            // Omit cookies is the wrong posture — NextAuth needs the session
            // cookie to prove identity. Default `credentials: 'same-origin'`
            // is correct here.
            keepalive: true,
        })
        if (!response.ok && process.env.NODE_ENV !== 'production') {
            // eslint-disable-next-line no-console
            console.warn(`[analytics] emit non-2xx for ${envelope.event_type}: ${response.status}`)
        }
    } catch (error) {
        if (process.env.NODE_ENV !== 'production') {
            // eslint-disable-next-line no-console
            console.warn(`[analytics] emit failed for ${envelope.event_type}:`, error)
        }
    }
}

/** Exposed for tests that need a known active_lever_filter shape. */
export type { ActiveLeverFilter }
