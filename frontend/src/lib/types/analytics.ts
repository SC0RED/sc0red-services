/**
 * sc0red CTA analytics event types — must stay in sync with the backend
 * Pydantic envelope in `backend/src/models/analytics_events.py`.
 *
 * The discriminated union is keyed on `source` rather than `event_type`
 * because the PDF render variant has structurally different requirements
 * (no `active_lever_filter`). Keeping them as separate TS types makes
 * the constraint compiler-enforceable: you cannot construct a PDF event
 * with a lever filter and have it typecheck.
 */

export const ANALYTICS_VERSION = '1'

export type AnalyticsEventType =
    | 'sc0red_cta_banner_expanded'
    | 'sc0red_cta_banner_collapsed'
    | 'sc0red_cta_clicked'
    | 'sc0red_cta_rendered_in_pdf'

export type WebAnalyticsEventType = Exclude<AnalyticsEventType, 'sc0red_cta_rendered_in_pdf'>

export type AnalyticsSource = 'web' | 'pdf'

export type ActiveLeverFilter = 'Revenue Side' | 'Cost Side'

interface BaseEnvelope {
    event_id: string
    timestamp: string
    analytics_version: typeof ANALYTICS_VERSION
    analysis_id: string
    opportunity_count: number
}

export interface WebAnalyticsEvent extends BaseEnvelope {
    event_type: WebAnalyticsEventType
    source: 'web'
    active_lever_filter: ActiveLeverFilter | null
}

export interface PdfAnalyticsEvent extends BaseEnvelope {
    event_type: 'sc0red_cta_rendered_in_pdf'
    source: 'pdf'
    active_lever_filter: null
}

export type AnalyticsEvent = WebAnalyticsEvent | PdfAnalyticsEvent

/** Context callers must supply — identity is added server-side from the JWT. */
export interface WebEventContext {
    analysisId: string
    opportunityCount: number
    activeLeverFilter: ActiveLeverFilter | null
}

export interface PdfEventContext {
    analysisId: string
    opportunityCount: number
}
