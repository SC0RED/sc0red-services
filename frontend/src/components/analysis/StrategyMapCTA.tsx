'use client'

import { useState } from 'react'

import { LoadingSpinner } from '@/components/ui'

interface StrategyMapCTAProps {
    analysisId: string
    /** Fired after the API returns 202 — caller flips the slot to the
     *  generating state and starts the AppSync subscription. */
    onGenerationStarted: () => void
    /** Optional: render a "Generation failed — try again" message above the
     *  button. Cleared on the next click. */
    failureMessage?: string | null
}

/**
 * "Generate strategy map" button + framing copy. Rendered in the absent
 * state of the strategy-map slot (per the strategy-map-on-demand spec
 * scenario "User clicking the CTA transitions to generating state").
 *
 * Click behaviour:
 *   1. POST /api/analysis/{id}/strategy-map
 *   2. On 202 → callback so the parent flips the slot to generating
 *   3. On non-202 → render an inline error and re-enable the button
 *
 * The 503 STRATEGY_MAP_FEATURE_DISABLED case (queue not provisioned in
 * this environment) is treated as a generic API error — frontend doesn't
 * differentiate. Operationally that case only happens during deployment
 * windows and the message is never surfaced to real customers.
 */
export default function StrategyMapCTA({
    analysisId,
    onGenerationStarted,
    failureMessage,
}: StrategyMapCTAProps) {
    const [isPending, setIsPending] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const handleClick = async () => {
        if (isPending) return
        setIsPending(true)
        setError(null)

        try {
            const response = await fetch(`/api/analysis/${analysisId}/strategy-map`, {
                method: 'POST',
            })
            if (response.status === 202) {
                onGenerationStarted()
                // No need to setIsPending(false) — the parent unmounts this
                // component when transitioning to the generating state.
                return
            }
            const body = (await response.json().catch(() => ({}))) as { error?: string }
            setError(body?.error ?? 'Could not start generation. Please try again in a moment.')
        } catch {
            setError('Network error. Please try again.')
        } finally {
            setIsPending(false)
        }
    }

    const visibleError = error ?? failureMessage ?? null

    return (
        <div
            className="card card--rich"
            data-testid="strategy-map-on-demand-cta"
            // `card--rich` provides the lock-in padding via the
            // `--card-padding-rich` token; only `text-align` is layered
            // on inline (no CSS modifier exists for centred-card).
            style={{ textAlign: 'center' }}
        >
            <h3 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '0.5rem' }}>Strategy map</h3>
            <p
                style={{
                    fontSize: '0.875rem',
                    color: 'var(--text-secondary)',
                    lineHeight: 1.6,
                    marginBottom: '1.25rem',
                    maxWidth: '480px',
                    marginLeft: 'auto',
                    marginRight: 'auto',
                }}
            >
                Synthesise a Balanced Scorecard view from the risks, opportunities, EBITDA, and value chain
                above. Grounded in the Vector Advisory framework.
            </p>
            {visibleError ? (
                <p
                    role="alert"
                    style={{
                        fontSize: '0.8125rem',
                        color: 'var(--risk-high)',
                        marginBottom: '0.75rem',
                    }}
                >
                    {visibleError}
                </p>
            ) : null}
            <button
                type="button"
                className="btn btn-primary"
                onClick={handleClick}
                disabled={isPending}
                aria-busy={isPending}
                data-testid="strategy-map-cta-button"
                style={{ minWidth: '200px' }}
            >
                {isPending ? (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                        <LoadingSpinner size="sm" />
                        Starting…
                    </span>
                ) : (
                    'Generate strategy map'
                )}
            </button>
        </div>
    )
}
