import type { CSSProperties } from 'react'

import OpportunityDotStrip from '@/components/analysis/OpportunityDotStrip'
import { useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import type { Opportunity } from '@/lib/types/api'

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
 *     value range inline. No opportunity dots, no description tooltip
 *     — subtotals don't carry those surfaces.
 *
 *   - ``isSubtotalHeading: false`` (default) — **compact chip**:
 *     dimensioned to fit beside its siblings inside the band row
 *     (~150-200 px wide, ~80-100 px tall). Surfaces the label,
 *     value range, percentage-of-parent, and the shared
 *     ``OpportunityDotStrip``. The long-form ``description`` is
 *     surfaced via the native HTML ``title`` attribute on the chip's
 *     outer element — no custom absolutely-positioned overlay (kills
 *     the overlap bug from the pre-``compact-ebitda-bands`` design).
 *
 * Confidence chip removed by P2 of the ``redesign-analysis-visuals``
 * change — see the ``ebitda-tree-confidence`` spec deltas. The
 * ``confidence_level`` / ``confidence_basis`` fields still flow on
 * ``EbitdaNode`` for any future surface (audit panel, debug overlay);
 * only the visual rendering was dropped.
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
    /** Index pointers into ``opportunities`` — same idiom the strategy
     *  map and value chain use. The shared ``OpportunityDotStrip``
     *  resolves them at render time. */
    linkedIndices: number[]
    /** Full opportunities array — required so the dot strip can colour
     *  each dot from the linked opportunity's ``value_lever``. */
    opportunities: Opportunity[]
    /** When ``true`` the component renders the band-header variant
     *  (single row, colored left strip, ``<h3>`` label, no surfaces
     *  beyond label + value range). When ``false`` (default) the
     *  component renders the compact-chip variant. */
    isSubtotalHeading?: boolean
}

/** Per-type semantic accent colors. After
 *  ``tighten-analysis-page-readability``, this map carries only the
 *  ``accent`` hex used on the band header's 4px left strip and the
 *  chip's 3px left border. The chip body, main border, and label all
 *  use theme tokens (``--bg-surface-2``, ``--border-subtle``,
 *  ``--text-primary``) — no more chromatic-bath chip backgrounds.
 */
const NODE_COLORS: Record<string, { accent: string }> = {
    revenue: { accent: '#22C55E' },
    cost: { accent: '#EF4444' },
    margin: { accent: '#3B7BF6' },
    subtotal: { accent: '#F59E0B' },
}

export default function EbitdaNodeComponent(props: EbitdaCardProps) {
    // The TypeScript discriminated union on ``type`` guarantees a hit
    // in ``NODE_COLORS`` — no fallback. A future contributor who adds
    // a new ``type`` value MUST add a ``NODE_COLORS`` entry; otherwise
    // they'll get a loud ``undefined.accent`` at render time instead
    // of a silently-wrong default.
    const { accent } = NODE_COLORS[props.type]
    if (props.isSubtotalHeading) {
        return <BandHeader {...props} accentColor={accent} />
    }
    return <LeafChip {...props} accentColor={accent} />
}

/** Band-header variant — one-row P&L subtotal anchor.
 *
 *  Visual treatment mirrors the strategy-map perspective-band
 *  headers: a thick colored left strip, the label in ``<h3>``, the
 *  value range surfaced inline to the right. No opportunity dots
 *  (subtotals don't carry ``linked_opportunity_indices`` in
 *  production). No description overlay (subtotal descriptions
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
                    fontSize: '1rem',
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
                        fontSize: '1rem',
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
 *  label / value range / percentage / opportunity-link dot strip. The
 *  leaf's long-form ``description`` is delivered via the native HTML
 *  ``title`` attribute on the chip itself — no custom overlay. */
function LeafChip({
    label,
    valueRange,
    percentageOfParent,
    description,
    linkedIndices,
    opportunities,
    accentColor,
}: EbitdaCardProps & { accentColor: string }) {
    // P5 hover-provider wiring (redesign-analysis-visuals): hovering /
    // focusing the chip publishes its ``linkedIndices`` to the shared
    // provider so the matching opportunity cards in OpportunitiesList
    // below pulse + scroll into view. ``useOpportunityHover`` returns
    // a no-op context when no provider is mounted (isolated tests,
    // print path), so the chip stays harmless outside the analysis page.
    const { highlightOpportunities, clearHighlight } = useOpportunityHover()
    const hasLinks = linkedIndices.length > 0
    const onEnter = () => {
        if (hasLinks) highlightOpportunities(linkedIndices)
    }
    // ``onBlur`` bubbles from any focusable descendant — the dot strip's
    // overflow ``+N`` badge has ``tabIndex={0}``, and if a future
    // contributor adds another focusable child, tabbing to it would
    // otherwise clear the highlight. Guard against the bubble.
    const onBlur = (event: React.FocusEvent<HTMLElement>) => {
        const next = event.relatedTarget as Node | null
        if (event.currentTarget.contains(next)) return
        clearHighlight()
    }
    return (
        <article
            // Chip MUST be reachable in keyboard tab order between the
            // band header above and the next connector below per
            // ``ebitda-impact-model`` spec. A chip with no opportunity
            // dots would otherwise have zero focusable surface and be
            // skipped by Tab navigation.
            tabIndex={0}
            // The native ``title`` attribute delivers the long-form
            // description as a browser tooltip when the chip is
            // hovered or focused. Replaces the custom absolutely-
            // positioned overlay that overflowed neighbouring rows.
            title={description || undefined}
            onMouseEnter={onEnter}
            onMouseLeave={clearHighlight}
            onFocus={onEnter}
            onBlur={onBlur}
            style={chipStyle(accentColor)}
        >
            <div style={chipLabelStyle}>{label}</div>
            {valueRange && (
                <div style={chipValueRowStyle}>
                    <span>{valueRange}</span>
                </div>
            )}
            {percentageOfParent != null && (
                <div style={chipPercentStyle}>{percentageOfParent}% of parent</div>
            )}
            <OpportunityDotStrip
                linkedIndices={linkedIndices}
                opportunities={opportunities}
                testId="ebitda-linked-opportunity-dots"
            />
        </article>
    )
}

// ── chip styles ─────────────────────────────────────────────────────────────

/** Chip outer style. After ``tighten-analysis-page-readability`` the
 *  chip's semantic-type signal is carried ONLY on the 3px left border;
 *  the body, main border, and label are neutral theme tokens. Mirrors
 *  the strategy-map chip's ``borderLeft`` accent pattern. */
function chipStyle(accentColor: string): CSSProperties {
    return {
        padding: '8px 12px',
        background: 'var(--bg-surface-2)',
        border: '1px solid var(--border-subtle)',
        borderLeft: `3px solid ${accentColor}`,
        borderRadius: '8px',
        minWidth: '150px',
        maxWidth: '200px',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
    }
}

const chipLabelStyle: CSSProperties = {
    fontSize: '0.875rem',
    fontWeight: 700,
    color: 'var(--text-primary)',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
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
