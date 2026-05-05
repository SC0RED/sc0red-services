'use client'

interface ReanalyzeProgressCardProps {
    /**
     * Latest progress label from the re-analyze pipeline. Displayed
     * verbatim under the heading. Falls back to "Starting pipeline..."
     * when the realtime hook hasn't surfaced its first label yet.
     */
    label?: string
    /**
     * Latest progress percentage (0-100) from the re-analyze pipeline.
     * Drives both the progress-bar width and the percent-complete
     * readout below it. `undefined` is treated as 0.
     */
    progress?: number
    /**
     * Optional DOM `id` for `aria-describedby` wiring from the trigger
     * button — when set on the consumer's button while progress is
     * visible, screen readers announce both the button label and the
     * current progress state on focus.
     */
    id?: string
}

/**
 * Extracted from `DocumentUpload` so the document-upload widget stays
 * under the 360-line frontend cap, and so the same progress display
 * can be reused from `FailedAnalysisView` (or any other future
 * "long-running re-analysis" surface) without copy-paste.
 *
 * Strictly presentational — no state, no side effects, no fetches.
 * The consuming component owns the `reanalyzing` boolean that decides
 * whether to render this card at all.
 */
export default function ReanalyzeProgressCard({ label, progress, id }: ReanalyzeProgressCardProps) {
    const pct = progress ?? 0
    return (
        <div
            id={id}
            data-testid="reanalyze-progress"
            className="card"
            role="status"
            aria-live="polite"
            style={{
                padding: '1.5rem',
                marginTop: '1rem',
                textAlign: 'center',
            }}
        >
            <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                Re-analyzing with documents...
            </h3>
            <p
                style={{
                    color: 'var(--text-secondary)',
                    fontSize: '0.875rem',
                    marginBottom: '1rem',
                }}
            >
                {label || 'Starting pipeline...'}
            </p>
            <div className="progress-bar" style={{ maxWidth: '360px', margin: '0 auto' }}>
                <div className="progress-fill" style={{ width: `${pct}%` }} />
            </div>
            <div
                style={{
                    marginTop: '0.5rem',
                    fontSize: '0.75rem',
                    color: 'var(--text-tertiary)',
                }}
            >
                {pct}% complete
            </div>
        </div>
    )
}
