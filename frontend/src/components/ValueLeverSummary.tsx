'use client'

import { LEVER_COLORS } from '@/lib/utils/leverColors'
import type { Opportunity } from '@/lib/types/api'

interface ValueLeverSummaryProps {
    opportunities: Opportunity[]
    activeLever: string
    onLeverChange: (lever: string) => void
}

export default function ValueLeverSummary({
    opportunities,
    activeLever,
    onLeverChange,
}: ValueLeverSummaryProps) {
    const hasValueLevers = opportunities.some((o) => o.value_lever)

    const leverSummary = hasValueLevers
        ? (['Revenue Side', 'Cost Side', 'Both'] as const).map((lever) => ({
              lever,
              count: opportunities.filter((o) => o.value_lever === lever).length,
          }))
        : []

    if (!hasValueLevers) return null

    return (
        <div style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem' }}>Value Impact</h2>
            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: '0.875rem',
                }}
            >
                {leverSummary.map(({ lever, count }) => {
                    const color = LEVER_COLORS[lever] || 'var(--text-secondary)'
                    return (
                        <button
                            key={lever}
                            type="button"
                            className="card"
                            aria-pressed={activeLever === lever}
                            style={{
                                padding: '1.25rem',
                                borderTop: `3px solid ${color}`,
                                cursor: 'pointer',
                                background: activeLever === lever ? `${color}10` : 'var(--bg-surface)',
                                textAlign: 'left',
                                width: '100%',
                            }}
                            onClick={() => onLeverChange(activeLever === lever ? 'All' : lever)}
                        >
                            <div
                                style={{
                                    fontSize: '0.8rem',
                                    color: 'var(--text-secondary)',
                                    marginBottom: '0.5rem',
                                }}
                            >
                                {lever}
                            </div>
                            <div style={{ fontSize: '1.75rem', fontWeight: 800, color }}>{count}</div>
                            <div
                                style={{
                                    fontSize: '0.75rem',
                                    color: 'var(--text-tertiary)',
                                    marginTop: '0.25rem',
                                }}
                            >
                                {count === 1 ? 'opportunity' : 'opportunities'}
                            </div>
                        </button>
                    )
                })}
            </div>
        </div>
    )
}
