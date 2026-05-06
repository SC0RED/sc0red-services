'use client'

import { LoadingSpinner } from '@/components/ui'

/**
 * Skeleton + status message rendered while the strategy-map worker is in
 * flight (per the strategy-map-on-demand spec scenario "Strategy map
 * generating state renders skeleton placeholder").
 *
 * No cancel button — the worker isn't reliably interruptible and we'd
 * rather not signal a control we can't honour. ~17s after Phase 1 of
 * optimize-strategy-map-latency lands; ~55s today.
 */
export default function StrategyMapGeneratingPlaceholder() {
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
                <span style={{ fontSize: '1rem', fontWeight: 600 }}>Generating your strategy map…</span>
            </div>
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
