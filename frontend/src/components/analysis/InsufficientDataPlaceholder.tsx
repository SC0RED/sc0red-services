'use client'

/**
 * Honest placeholder for a FACT report surface that could not be grounded.
 *
 * Part of the fact-vs-forecast data-integrity contract (report-data-integrity
 * spec): when an existing fact (the financial model, the operating model) cannot
 * be established from public information, we render this instead of fabricating
 * a default. The optional CTA is a clickable control that takes the reader to the
 * document-upload widget so they can supply data and re-analyse — the same
 * widget that already lives at the bottom of the analysis page (`#document-upload`).
 */
interface InsufficientDataPlaceholderProps {
    /** Short, deliberate heading — e.g. "Financial model not shown". */
    heading: string
    /** 1–2 sentences explaining why and reaffirming the grounding principle. */
    body: string
    /** CTA label. When omitted, no CTA renders. */
    ctaLabel?: string
    /** Invoked when the CTA is clicked (e.g. scroll to the upload widget). */
    onCtaClick?: () => void
    /** testid for the wrapper so section tests can assert the placeholder. */
    testId?: string
}

export default function InsufficientDataPlaceholder({
    heading,
    body,
    ctaLabel,
    onCtaClick,
    testId,
}: InsufficientDataPlaceholderProps) {
    return (
        <div
            className="card card--rich"
            data-testid={testId ?? 'insufficient-data-placeholder'}
            style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}
        >
            <strong style={{ fontSize: '1rem' }}>{heading}</strong>
            <p style={{ margin: 0, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{body}</p>
            {ctaLabel && onCtaClick && (
                <button
                    type="button"
                    className="btn-secondary"
                    onClick={onCtaClick}
                    style={{ alignSelf: 'flex-start' }}
                    data-testid="insufficient-data-cta"
                >
                    {ctaLabel}
                </button>
            )}
        </div>
    )
}
