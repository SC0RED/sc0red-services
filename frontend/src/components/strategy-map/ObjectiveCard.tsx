import type { ConfidenceMarker } from '@/lib/types/api'
import ConfidenceChip from './ConfidenceChip'

interface ObjectiveCardProps {
    /** Objective ID (e.g. F1, C2, I1.3, O.P) — used for cross-section linkage. */
    id: string
    /** Objective title. For Customer-perspective objectives, the renderer
     * wraps the title in quotation marks (Vector house style). */
    title: string
    definition: string
    confidence: ConfidenceMarker
    /** When true, the title is rendered as a first-person customer-voice quote. */
    customerVoice?: boolean
    /** Optional left-border accent colour (used by Internal Processes themes
     * to colour-code by category). */
    accentColor?: string
}

/**
 * One objective on the strategy map.
 *
 * Renders the ID as a small monospaced prefix (so cross-references
 * from arrows + gaps stay readable), the title as the headline, the
 * full definition paragraph below, and a confidence chip in the
 * top-right.
 *
 * Customer-perspective objectives use first-person customer voice
 * with surrounding quote marks (Vector house style); other
 * perspectives use plain titles.
 */
export default function ObjectiveCard({
    id,
    title,
    definition,
    confidence,
    customerVoice = false,
    accentColor,
}: ObjectiveCardProps) {
    return (
        <article
            className="strategy-map-objective-card"
            style={{
                padding: '14px 16px',
                background: 'var(--bg-surface-2)',
                border: '1px solid var(--border-subtle)',
                borderLeft: accentColor ? `3px solid ${accentColor}` : '1px solid var(--border-subtle)',
                borderRadius: '8px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
            }}
        >
            <header
                style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'space-between',
                    gap: '12px',
                }}
            >
                <div style={{ flex: 1 }}>
                    <span
                        style={{
                            fontFamily: 'var(--font-mono, monospace)',
                            fontSize: '0.7rem',
                            fontWeight: 600,
                            color: 'var(--text-tertiary)',
                            marginRight: '8px',
                        }}
                    >
                        {id}
                    </span>
                    <span
                        style={{
                            fontSize: '0.95rem',
                            fontWeight: 700,
                            lineHeight: 1.35,
                            color: 'var(--text-primary)',
                        }}
                    >
                        {customerVoice ? `"${title}"` : title}
                    </span>
                </div>
                <ConfidenceChip confidence={confidence} />
            </header>
            <p
                style={{
                    fontSize: '0.85rem',
                    lineHeight: 1.7,
                    color: customerVoice ? 'var(--text-primary)' : 'var(--text-secondary)',
                    margin: 0,
                    fontStyle: customerVoice ? 'italic' : 'normal',
                    whiteSpace: 'pre-line',
                }}
            >
                {definition}
            </p>
        </article>
    )
}
