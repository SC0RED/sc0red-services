import type { ConfidenceMarker } from '@/lib/types/api'

interface ConfidenceChipProps {
    confidence: ConfidenceMarker
}

/**
 * Small visual chip rendering the AI's per-objective confidence.
 *
 * The presence of confidence markers is part of the credibility of
 * the strategy map — prospects can see what's grounded vs. inferred.
 * That honesty is what earns the deep-dive conversation.
 *
 * - HIGH   — directly inferred from concrete public data
 * - MEDIUM — typical of similar companies; pattern-matched
 * - LOW    — inferred from absence; deep-dive candidate
 */
export default function ConfidenceChip({ confidence }: ConfidenceChipProps) {
    const palette = CONFIDENCE_PALETTE[confidence]
    return (
        <span
            style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '2px 8px',
                borderRadius: '999px',
                fontSize: '0.65rem',
                fontWeight: 700,
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
                background: palette.background,
                color: palette.color,
                border: `1px solid ${palette.border}`,
                lineHeight: 1.4,
            }}
            title={palette.tooltip}
        >
            {confidence}
        </span>
    )
}

const CONFIDENCE_PALETTE: Record<
    ConfidenceMarker,
    { background: string; color: string; border: string; tooltip: string }
> = {
    HIGH: {
        background: 'var(--risk-low-bg)',
        color: 'var(--risk-low)',
        border: 'var(--risk-low)',
        tooltip: 'Directly inferred from concrete public data.',
    },
    MEDIUM: {
        background: 'var(--risk-moderate-bg)',
        color: 'var(--risk-moderate)',
        border: 'var(--risk-moderate)',
        tooltip: 'Typical of similar companies in this industry; pattern-matched but not directly observed.',
    },
    LOW: {
        background: 'var(--bg-surface-3)',
        color: 'var(--text-tertiary)',
        border: 'var(--border)',
        tooltip: 'Inferred from absence; reasonable but unverified — deep-dive candidate.',
    },
}
