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

/*
 * Strategy-map deep-dive CTA event types.
 *
 *   sc0red_cta_rendered_strategy_map — fires on component mount
 *     (the CTA is always-visible below the strategy map).
 *   sc0red_cta_clicked_strategy_map  — fires on the contact-link click.
 *
 * Both are web-source. The backend model_validator enforces
 * active_lever_filter=null for these (no lever-filter concept on the
 * strategy-map surface; non-null would corrupt cross-surface funnel
 * queries that join on event_type). Callers MUST pass
 * activeLeverFilter as null.
 *
 * IMPORTANT — keep the union body below comment-free:
 * scripts/check_analytics_type_parity.py extracts string literals from
 * the union with a regex that does NOT understand // line comments.
 * Apostrophes inside such a comment (e.g. "backend's") look like
 * opening quotes to the parser and pull garbage between them into the
 * extracted set, breaking parity. Put narrative here, members below.
 */
export type AnalyticsEventType =
    | 'sc0red_cta_rendered_in_pdf'
    | 'sc0red_cta_rendered_strategy_map'
    | 'sc0red_cta_clicked_strategy_map'

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
