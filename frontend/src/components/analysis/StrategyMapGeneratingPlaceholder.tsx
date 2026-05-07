'use client'

import { LoadingSpinner } from '@/components/ui'

interface StrategyMapGeneratingPlaceholderProps {
    /** Optional in-flight progress reported by the worker via AppSync.
     *  When provided, replaces the static spinner with a moving bar
     *  showing percentage + the worker's current phase label.
     *  ``null`` keeps the legacy static-spinner UX (used while the
     *  worker hasn't reported yet, or when AppSync is unconfigured). */
    progress?: { percentage: number; label: string } | null
}

/**
 * Skeleton + status message rendered while the strategy-map worker is in
 * flight (per the strategy-map-on-demand spec scenario "Strategy map
 * generating state renders skeleton placeholder").
 *
 * No cancel button — the worker isn't reliably interruptible and we'd
 * rather not signal a control we can't honour. The progress bar is
 * driven by phase-boundary AppSync events from the worker — see
 * `notify_strategy_map_progress` in `appsync_notifier.py` and
 * `useStrategyMapSubscription`'s `onProgress` callback.
 */
export default function StrategyMapGeneratingPlaceholder({
    progress = null,
}: StrategyMapGeneratingPlaceholderProps = {}) {
    const headerLabel = progress?.label ?? 'Generating your strategy map…'
    return (
        <div
            className="card card--rich"
            data-testid="strategy-map-generating"
            // `card--rich` provides the lock-in padding via the
            // `--card-padding-rich` token; only `text-align` is layered
            // on inline (no CSS modifier exists for centred-card).
            style={{ textAlign: 'center' }}
        >
            <div
                style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.625rem',
                    marginBottom: '1rem',
                }}
            >
                <LoadingSpinner size="md" />
                <span style={{ fontSize: '1rem', fontWeight: 600 }}>{headerLabel}</span>
            </div>
            {progress
                ? (() => {
                      // Clamp once and use the clamped value for both the
                      // rendered fill width AND the ARIA-exposed value, so a
                      // malformed worker event (e.g. progress=150) doesn't
                      // make screen readers announce "150 out of 100" (which
                      // violates the ARIA spec's
                      // `aria-valuemin <= aria-valuenow <= aria-valuemax`
                      // constraint).
                      const clamped = Math.max(0, Math.min(100, progress.percentage))
                      return (
                          <div
                              role="progressbar"
                              aria-valuenow={clamped}
                              aria-valuemin={0}
                              aria-valuemax={100}
                              aria-label="Strategy map generation progress"
                              data-testid="strategy-map-generating-progress"
                              style={{
                                  width: '100%',
                                  maxWidth: '440px',
                                  marginLeft: 'auto',
                                  marginRight: 'auto',
                                  marginBottom: '0.75rem',
                                  height: '6px',
                                  background: 'var(--bg-surface-2)',
                                  borderRadius: '3px',
                                  overflow: 'hidden',
                              }}
                          >
                              <div
                                  style={{
                                      width: `${clamped}%`,
                                      height: '100%',
                                      background: 'var(--accent-blue)',
                                      transition: 'width 400ms ease',
                                  }}
                              />
                          </div>
                      )
                  })()
                : null}
            <p
                style={{
                    fontSize: '0.8125rem',
                    color: 'var(--text-secondary)',
                    lineHeight: 1.6,
                    maxWidth: '440px',
                    marginLeft: 'auto',
                    marginRight: 'auto',
                }}
            >
                Synthesising the diagnosis. This usually takes under a minute. You can navigate away — the
                result will be here when you come back.
            </p>
        </div>
    )
}
