'use client'

import { useEffect } from 'react'

import { emit } from '@/lib/analytics/emitEvent'
import { getSc0redContactUrl } from '@/lib/config'

/** Placement on the analysis page. Drives the analytics event names
 *  and the outbound URL's ``?source=`` query parameter so the funnel
 *  can attribute impressions + clicks to the right surface. Added in
 *  Phase 11 of ``redesign-analysis-visuals`` to fix the analytics
 *  conflation bug (the bottom CTA was previously firing the
 *  strategy-map event names regardless of placement, double-counting
 *  the strategy-map funnel). */
export type DeepDiveCTAPlacement = 'strategy-map' | 'analysis-end'

interface DeepDiveCTAProps {
    /** Analysis ID — appended as `analysis-id={id}` query param for funnel attribution. */
    analysisId: string
    /** Optional gap ID — when provided, appended as `gap={id}`. Used by per-gap CTA variants. */
    gapId?: string
    /** Variant — `headline` is the prominent CTA below the strategy map; `inline`
     * is the smaller per-gap variant (not used in v1 but supported for future). */
    variant?: 'headline' | 'inline'
    /** Where on the page this CTA renders. Drives event-name + ``?source=``
     *  attribution. Defaults to ``strategy-map`` for backwards compatibility
     *  with the single-placement call sites that pre-date Phase 11. */
    placement?: DeepDiveCTAPlacement
}

/**
 * "Contact us for deep dive" CTA — links to the existing sc0red
 * contact form with funnel-attribution query parameters.
 *
 * Renders in two placements on the analysis page:
 *
 *   - ``strategy-map`` (default) — under the strategy-map table when
 *     the map is present.
 *   - ``analysis-end`` — at the bottom of the page on every successful
 *     analysis.
 *
 * The ``placement`` prop switches:
 *   - The analytics event names (``_rendered_strategy_map`` /
 *     ``_clicked_strategy_map`` vs ``_rendered_analysis_end`` /
 *     ``_clicked_analysis_end``).
 *   - The outbound URL's ``?source=`` query parameter (``strategy-map``
 *     vs ``analysis-end``).
 *
 * Without per-placement event names, funnel queries grouped by
 * event_type would double-count the strategy-map funnel by mixing in
 * the bottom-CTA's impressions and clicks. See
 * ``analysis-detail-narrative`` spec requirement "DeepDiveCTA
 * distinguishes placement in analytics".
 *
 * The contact form already exists at the company level; v1 reuses it
 * (no new form infrastructure). Future iterations could replace with
 * an embedded form, Calendly, or a custom modal — the component's
 * ``href`` is the only thing that changes.
 *
 * Emits two analytics events via ``POST /api/analytics/events`` per
 * placement: one on mount (always-visible CTA, mount is the right
 * "saw the CTA" signal) and one on the anchor's click (fire-and-
 * forget; navigation is not blocked).
 *
 * Neither surface carries a lever filter, so emits pass
 * ``activeLeverFilter: null`` and ``opportunityCount: 0`` — funnel
 * queries should scope on ``event_type`` rather than these fields.
 */
export default function DeepDiveCTA({
    analysisId,
    gapId,
    variant = 'headline',
    placement = 'strategy-map',
}: DeepDiveCTAProps) {
    const href = buildContactUrl(analysisId, placement, gapId)

    const renderedEvent =
        placement === 'analysis-end' ? 'sc0red_cta_rendered_analysis_end' : 'sc0red_cta_rendered_strategy_map'
    const clickedEvent =
        placement === 'analysis-end' ? 'sc0red_cta_clicked_analysis_end' : 'sc0red_cta_clicked_strategy_map'

    const analyticsContext = {
        analysisId,
        // The CTA is not anchored to opportunities — pass 0 rather than
        // overloading the field with an unrelated count. Funnel queries
        // should scope on event_type, not opportunity_count.
        opportunityCount: 0,
        activeLeverFilter: null,
    }

    useEffect(() => {
        // One emit per mount, scoped to (analysisId, placement). If the
        // user navigates away and back the effect re-fires; that's the
        // desired "saw the CTA" granularity. Fire-and-forget; emit
        // failures never block UI (see emitEvent.ts).
        //
        // ``gapId`` is intentionally OMITTED from the dependency array
        // and from the analytics payload in v1: the inline (per-gap)
        // variant is not yet rendered in production. When per-gap CTAs
        // do ship, extend ``WebEventContext`` with ``gapId``.
        void emit(renderedEvent, analyticsContext)
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [analysisId, placement])

    const handleCtaClick = () => {
        // Fire-and-forget. The browser dispatches the anchor's default
        // navigation as soon as this handler returns; ``keepalive: true``
        // inside ``emit()`` ensures the POST survives the new-tab open.
        void emit(clickedEvent, analyticsContext)
    }

    if (variant === 'inline') {
        return (
            <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                onClick={handleCtaClick}
                style={{
                    fontSize: '0.875rem',
                    color: 'var(--accent-blue)',
                    fontWeight: 600,
                    textDecoration: 'none',
                }}
            >
                Discuss in a deep dive →
            </a>
        )
    }

    return (
        <section
            data-testid={placement === 'analysis-end' ? 'analysis-end-cta' : 'strategy-map-cta'}
            style={{
                marginTop: '20px',
                padding: '20px 24px',
                background: 'var(--accent-blue-glow)',
                border: '1px solid var(--accent-blue)',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '16px',
                flexWrap: 'wrap',
            }}
        >
            <div style={{ flex: '1 1 320px', minWidth: '0' }}>
                <h3
                    style={{
                        fontSize: '1rem',
                        fontWeight: 700,
                        margin: '0 0 6px',
                        color: 'var(--text-primary)',
                    }}
                >
                    Want a deeper analysis?
                </h3>
                <p
                    style={{
                        fontSize: '0.875rem',
                        color: 'var(--text-secondary)',
                        margin: 0,
                        lineHeight: 1.6,
                    }}
                >
                    sc0red Advisory&rsquo;s deep-dive engagement validates the strategic hypotheses in this
                    map and translates the objectives into measures, targets, and named initiatives.
                </p>
            </div>
            <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                onClick={handleCtaClick}
                style={{
                    flex: '0 0 auto',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '10px 18px',
                    borderRadius: '6px',
                    background: 'var(--accent-blue)',
                    color: 'white',
                    fontSize: '0.875rem',
                    fontWeight: 600,
                    textDecoration: 'none',
                }}
            >
                Contact us for deep dive
                <span aria-hidden="true">→</span>
            </a>
        </section>
    )
}

function buildContactUrl(analysisId: string, placement: DeepDiveCTAPlacement, gapId?: string): string {
    const base = getSc0redContactUrl()
    const params = new URLSearchParams({
        source: placement,
        'analysis-id': analysisId,
    })
    if (gapId) params.set('gap', gapId)
    // The contact URL may already have a query string — preserve it.
    const separator = base.includes('?') ? '&' : '?'
    return `${base}${separator}${params.toString()}`
}
