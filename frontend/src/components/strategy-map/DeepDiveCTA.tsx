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
 */
export default function DeepDiveCTA({ analysisId, gapId, variant = 'headline' }: DeepDiveCTAProps) {
    const href = buildContactUrl(analysisId, gapId)

    if (variant === 'inline') {
        return (
            <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                    fontSize: '0.85rem',
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
                        fontSize: '1.05rem',
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
                    Vector Advisory&rsquo;s deep-dive engagement validates the strategic hypotheses in this
                    map and translates the objectives into measures, targets, and named initiatives.
                </p>
            </div>
            <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                    flex: '0 0 auto',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '10px 18px',
                    borderRadius: '6px',
                    background: 'var(--accent-blue)',
                    color: 'white',
                    fontSize: '0.9rem',
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
