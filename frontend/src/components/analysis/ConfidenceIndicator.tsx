import type { ConfidenceMarker } from '@/lib/types/api'
import { capitalise } from '@/lib/utils/stringUtils'

interface ConfidenceIndicatorProps {
    confidence: ConfidenceMarker
    /**
     * Visual size variant.
     *   - `'small'` — ~6px dots, for inline contexts like a chip's
     *     compact header. No tooltip-on-hover (less inviting in
     *     header context where many chips compete for attention).
     *   - `'default'` — ~10px dots with tooltip-on-hover for the
     *     long-form rationale. Used in tooltip bodies and any other
     *     full-detail surface.
     */
    size?: 'small' | 'default'
}

/**
 * Visual indicator for AI-inferred confidence (HIGH / MEDIUM / LOW)
 * on objectives, opportunities, and any other AI output where the
 * backend emits a `ConfidenceMarker`.
 *
 * Renders a 3-dot scale in a single neutral color:
 *
 *   HIGH    →  ●●●    (3 filled, 0 hollow)
 *   MEDIUM  →  ●●○    (2 filled, 1 hollow)
 *   LOW     →  ●○○    (1 filled, 2 hollow)
 *
 * The neutral palette is intentional. The page's risk-tier system
 * (low / moderate / high / critical) uses green / amber / red — green
 * meaning "low risk" (good). Confidence runs in the OPPOSITE direction:
 * high confidence is good. Reusing the risk-tier palette for confidence
 * caused readers to conflate "HIGH confidence in this objective" with
 * "high risk for this company." The two signals share neither concept
 * nor direction; they shouldn't share a palette.
 *
 * Replaces the legacy `<ConfidenceChip>` component, which used the
 * risk-tier palette. See `ai-output-trust-markers` design D1 + D2 for
 * the rationale.
 *
 * Accessibility: the wrapper carries `aria-label="Confidence: {level}"`
 * so screen-reader users hear the level by name. The dots are
 * `aria-hidden` because their meaning is conveyed by the aria-label;
 * announcing them individually would be noisy.
 */
export default function ConfidenceIndicator({ confidence, size = 'default' }: ConfidenceIndicatorProps) {
    const filledCount = FILLED_DOTS[confidence]
    const dotSize = size === 'small' ? 6 : 10
    const gap = size === 'small' ? 2 : 4
    const tooltip = size === 'default' ? CONFIDENCE_TOOLTIP[confidence] : undefined
    const levelLabel = capitalise(confidence.toLowerCase())

    return (
        <span
            aria-label={`Confidence: ${levelLabel}`}
            title={tooltip}
            style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: `${gap}px`,
            }}
        >
            {[0, 1, 2].map((index) => {
                const isFilled = index < filledCount
                return (
                    <span
                        key={index}
                        aria-hidden="true"
                        style={{
                            width: `${dotSize}px`,
                            height: `${dotSize}px`,
                            borderRadius: '50%',
                            background: isFilled ? 'var(--text-secondary)' : 'transparent',
                            border: isFilled ? '1px solid var(--text-secondary)' : '1px solid var(--border)',
                            flexShrink: 0,
                        }}
                    />
                )
            })}
        </span>
    )
}

const FILLED_DOTS: Record<ConfidenceMarker, number> = {
    HIGH: 3,
    MEDIUM: 2,
    LOW: 1,
}

const CONFIDENCE_TOOLTIP: Record<ConfidenceMarker, string> = {
    HIGH: 'Directly inferred from concrete public data.',
    MEDIUM: 'Typical of similar companies in this industry; pattern-matched but not directly observed.',
    LOW: 'Inferred from absence; reasonable but unverified — deep-dive candidate.',
}
