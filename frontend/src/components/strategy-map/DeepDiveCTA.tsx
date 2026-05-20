'use client'

import { useEffect } from 'react'

import { emit } from '@/lib/analytics/emitEvent'
import { getSc0redContactUrl } from '@/lib/config'

interface DeepDiveCTAProps {
    /** Analysis ID — appended as `analysis-id={id}` query param for funnel attribution. */
    analysisId: string
    /** Optional gap ID — when provided, appended as `gap={id}`. Used by per-gap CTA variants. */
    gapId?: string
    /** Variant — `headline` is the prominent CTA below the strategy map; `inline`
     * is the smaller per-gap variant (not used in v1 but supported for future). */
    variant?: 'headline' | 'inline'
}

/**
 * "Contact us for deep dive" CTA — links to the existing sc0red
 * contact form with funnel-attribution query parameters.
 *
 * Spec: links to `https://www.sc0red.com/contact?source=strategy-map&analysis-id={id}`.
 * Per-gap CTAs additionally include `&gap={gapId}`.
 *
 * The contact form already exists at the company level; v1 reuses
 * it (no new form infrastructure). Future iterations could replace
 * with an embedded form, Calendly, or a custom modal — the
 * component's `href` is the only thing that changes.
 *
 * Emits two analytics events via `POST /api/analytics/events`:
 * - `sc0red_cta_rendered_strategy_map` — fired on mount via
 *   `useEffect`. The strategy-map CTA is always-visible (no
 *   expand/collapse), so mount is the right "saw the CTA" signal.
 * - `sc0red_cta_clicked_strategy_map` — fired in the anchor's
 *   `onClick`. Fire-and-forget; navigation is not blocked by the
 *   emit (the analytics POST silently drops on transient failure
 *   so the click is never lost to a flaky network).
 *
 * The strategy-map surface has no lever-filter concept, so emits
 * pass `activeLeverFilter: null`. `opportunityCount` is also `0` —
 * the field belongs to the opportunities funnel, not the
 * strategy-map funnel; funnel queries should scope on `event_type`.
 */
export default function DeepDiveCTA({ analysisId, gapId, variant = 'headline' }: DeepDiveCTAProps) {
    const href = buildContactUrl(analysisId, gapId)

    const analyticsContext = {
        analysisId,
        // The strategy-map CTA is not anchored to opportunities — pass 0
        // rather than overloading the field with an unrelated count.
        // Funnel queries should scope on event_type, not opportunity_count.
        opportunityCount: 0,
        activeLeverFilter: null,
    }

    useEffect(() => {
        // One emit per mount, scoped to `analysisId`. If the user
        // navigates away and back the effect re-fires; that's the
        // desired "saw the CTA" granularity. Fire-and-forget; emit
        // failures never block UI (see emitEvent.ts).
        //
        // `gapId` is intentionally OMITTED from the dependency array
        // and from the analytics payload in v1: the inline (per-gap)
        // variant is not yet rendered in production (only the
        // headline CTA on AnalysisDetail is wired up — see
        // DeepDiveCTAProps.variant docstring). When per-gap CTAs do
        // ship, the right move is to extend `WebEventContext` with
        // `gapId` and add it here so multi-gap views produce
        // distinct impression events. Until then, a `gapId`-only
        // re-render does NOT re-emit, and that's deliberate — the
        // current `_rendered_strategy_map` event is an
        // analysis-level impression signal, not a per-gap one.
        void emit('sc0red_cta_rendered_strategy_map', analyticsContext)
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [analysisId])

    const handleCtaClick = () => {
        // Fire-and-forget. The browser dispatches the anchor's default
        // navigation as soon as this handler returns; `keepalive: true`
        // inside `emit()` ensures the POST survives the new-tab open.
        void emit('sc0red_cta_clicked_strategy_map', analyticsContext)
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
            data-testid="strategy-map-cta"
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

function buildContactUrl(analysisId: string, gapId?: string): string {
    const base = getSc0redContactUrl()
    const params = new URLSearchParams({
        source: 'strategy-map',
        'analysis-id': analysisId,
    })
    if (gapId) params.set('gap', gapId)
    // The contact URL may already have a query string — preserve it.
    const separator = base.includes('?') ? '&' : '?'
    return `${base}${separator}${params.toString()}`
}
