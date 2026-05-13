import type { CSSProperties } from 'react'

import ConfidenceIndicator from '@/components/analysis/ConfidenceIndicator'
import { LEVER_COLORS } from '@/lib/utils/leverColors'

/**
 * Single P&L line-item used by the EBITDA Impact Model section.
 *
 * The component branches on ``isSubtotalHeading`` between two
 * structurally different variants (per ``ebitda-impact-model``
 * Modified Requirements after the ``compact-ebitda-bands`` change):
 *
 *   - ``isSubtotalHeading: true`` — **band header**: a single-row
 *     element with a colored left-edge strip, the subtotal label in
 *     ``<h3>`` (preserves screen-reader heading navigation), and the
 *     value range inline. No confidence chip, no opportunity dots,
 *     no description tooltip — subtotals don't carry those surfaces.
 *
 *   - ``isSubtotalHeading: false`` (default) — **compact chip**:
 *     dimensioned to fit beside its siblings inside the band row
 *     (~150-200 px wide, ~80-100 px tall). Surfaces the label,
 *     value range, percentage-of-parent, ``ConfidenceIndicator``,
 *     and opportunity-link indicator dots. The long-form
 *     ``description`` is surfaced via the native HTML ``title``
 *     attribute on the chip's outer element — no custom
 *     absolutely-positioned overlay (kills the overlap bug from
 *     the pre-``compact-ebitda-bands`` design).
 *
 * Both variants share the same ``NODE_COLORS`` palette keyed on
 * ``type``.
 */
export interface EbitdaCardProps {
    label: string
    type: 'revenue' | 'cost' | 'margin' | 'subtotal'
    valueRange?: string
    percentageOfParent?: number
    description: string
    linkedOpportunities: Array<{ title: string; valueLever: string }>
    /** Derivation-provenance level emitted by the backend. ``null`` /
     *  undefined suppresses the chip (no "unknown" badge — silence is
     *  more honest). */
    confidenceLevel?: 'high' | 'medium' | 'low' | null
    /** Human-readable explanation of which build inputs drove the
     *  figure; surfaced as a native ``title`` tooltip on the chip. */
    confidenceBasis?: string | null
    /** When ``true`` the component renders the band-header variant
     *  (single row, colored left strip, ``<h3>`` label, no surfaces
     *  beyond label + value range). When ``false`` (default) the
     *  component renders the compact-chip variant. */
    isSubtotalHeading?: boolean
}

const NODE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
    revenue: {
        bg: 'rgba(34, 197, 94, 0.10)',
        border: 'rgba(34, 197, 94, 0.35)',
        text: '#22C55E',
    },
    cost: {
        bg: 'rgba(239, 68, 68, 0.10)',
        border: 'rgba(239, 68, 68, 0.35)',
        text: '#EF4444',
    },
    margin: {
        bg: 'rgba(59, 123, 246, 0.10)',
        border: 'rgba(59, 123, 246, 0.35)',
        text: '#3B7BF6',
    },
    subtotal: {
        bg: 'rgba(245, 158, 11, 0.10)',
        border: 'rgba(245, 158, 11, 0.35)',
        text: '#F59E0B',
    },
}

export default function EbitdaNodeComponent(props: EbitdaCardProps) {
    // The TypeScript discriminated union on ``type`` guarantees a hit
    // in ``NODE_COLORS`` — no fallback. A future contributor who adds
    // a new ``type`` value MUST add a ``NODE_COLORS`` entry; otherwise
    // they'll get a loud ``undefined.text`` at render time instead of
    // a silently-wrong blue palette.
    const colors = NODE_COLORS[props.type]
    if (props.isSubtotalHeading) {
        return <BandHeader {...props} accentColor={colors.text} />
    }
    return <LeafChip {...props} colors={colors} />
}

/** Band-header variant — one-row P&L subtotal anchor.
 *
 *  Visual treatment mirrors the strategy-map perspective-band
 *  headers: a thick colored left strip, the label in ``<h3>``, the
 *  value range surfaced inline to the right. No confidence chip
 *  (subtotals carry no own confidence per ``ebitda-tree-confidence``).
 *  No opportunity dots (subtotals don't carry ``linked_opportunity_indices``
 *  in production). No description overlay (subtotal descriptions
 *  duplicate the band's role). */
function BandHeader({ label, valueRange, accentColor }: EbitdaCardProps & { accentColor: string }) {
    return (
        <div
            style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '10px 14px',
                borderLeft: `4px solid ${accentColor}`,
                background: 'var(--bg-surface-2, rgba(255,255,255,0.02))',
                borderRadius: '6px',
                width: '100%',
            }}
        >
            <h3
                style={{
                    margin: 0,
                    fontSize: '0.95rem',
                    fontWeight: 700,
                    color: accentColor,
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    flex: '0 0 auto',
                }}
            >
                {label}
            </h3>
            {valueRange && (
                <span
                    style={{
                        marginLeft: 'auto',
                        fontSize: '0.95rem',
                        fontWeight: 600,
                        color: 'var(--text-primary)',
                    }}
                >
                    {valueRange}
                </span>
            )}
        </div>
    )
}

/** Compact-chip variant — leaf driver of a subtotal.
 *
 *  ~150-180 px wide, ~80-100 px tall. Surfaces:
 *  label / value range / percentage / confidence indicator /
 *  opportunity-link dot row. The leaf's long-form ``description``
 *  is delivered via the native HTML ``title`` attribute on the chip
 *  itself — no custom overlay. */
function LeafChip({
    label,
    type,
    valueRange,
    percentageOfParent,
    description,
    linkedOpportunities,
    confidenceLevel,
    confidenceBasis,
    colors,
}: EbitdaCardProps & { colors: (typeof NODE_COLORS)[string] }) {
    // Show a confidence chip when the backend supplied a level AND
    // this is a leaf (revenue/cost) node. Subtotal / margin rollups
    // carry no own confidence per ebitda-tree-confidence.
    const showConfidenceChip =
        (confidenceLevel === 'high' || confidenceLevel === 'medium' || confidenceLevel === 'low') &&
        type !== 'subtotal' &&
        type !== 'margin'

    return (
        <article
            // Chip MUST be reachable in keyboard tab order between the
            // band header above and the next connector below per
            // ``ebitda-impact-model`` spec. A chip with no confidence
            // chip + no opportunity dots would otherwise have zero
            // focusable surface and be skipped by Tab navigation.
            tabIndex={0}
            // The native ``title`` attribute delivers the long-form
            // description as a browser tooltip when the chip is
            // hovered or focused. Replaces the custom absolutely-
            // positioned overlay that overflowed neighbouring rows.
            title={description || undefined}
            style={chipStyle(colors)}
        >
            <div style={chipLabelStyle(colors.text)}>{label}</div>
            {valueRange && (
                <div style={chipValueRowStyle}>
                    <span>{valueRange}</span>
                    {showConfidenceChip && confidenceLevel && (
                        <span
                            data-testid="ebitda-confidence-chip"
                            tabIndex={0}
                            // The chip's ``aria-label`` already comes from
                            // ``ConfidenceIndicator``; the native ``title``
                            // here adds the basis text for sighted users.
                            title={confidenceBasis ?? undefined}
                            style={{ display: 'inline-flex', cursor: 'help' }}
                        >
                            <ConfidenceIndicator
                                confidence={confidenceLevel.toUpperCase() as 'HIGH' | 'MEDIUM' | 'LOW'}
                                size="small"
                            />
                        </span>
                    )}
                </div>
            )}
            {percentageOfParent != null && (
                <div style={chipPercentStyle}>{percentageOfParent}% of parent</div>
            )}
            {linkedOpportunities.length > 0 && (
                <div data-testid="ebitda-linked-opportunity-dots" style={chipOpportunityDotRowStyle}>
                    {linkedOpportunities.map((opp, i) => (
                        <div
                            key={i}
                            style={{
                                width: '8px',
                                height: '8px',
                                borderRadius: '50%',
                                background: LEVER_COLORS[opp.valueLever] || 'var(--text-secondary)',
                            }}
                            title={`${opp.title} (${opp.valueLever})`}
                        />
                    ))}
                </div>
            )}
        </article>
    )
}

// ── chip styles ─────────────────────────────────────────────────────────────

function chipStyle(colors: (typeof NODE_COLORS)[string]): CSSProperties {
    return {
        padding: '8px 12px',
        background: colors.bg,
        border: `1px solid ${colors.border}`,
        borderRadius: '8px',
        minWidth: '150px',
        maxWidth: '200px',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
    }
}

function chipLabelStyle(textColor: string): CSSProperties {
    return {
        fontSize: '0.8125rem',
        fontWeight: 700,
        color: textColor,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
    }
}

const chipValueRowStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '0.875rem',
    fontWeight: 600,
    color: 'var(--text-primary)',
}

const chipPercentStyle: CSSProperties = {
    fontSize: '0.75rem',
    color: 'var(--text-secondary)',
}

const chipOpportunityDotRowStyle: CSSProperties = {
    display: 'flex',
    gap: '4px',
    flexWrap: 'wrap',
}
