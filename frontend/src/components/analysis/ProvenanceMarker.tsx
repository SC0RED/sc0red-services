interface ProvenanceMarkerProps {
    /**
     * The provenance kind. Drives label + tooltip text.
     *
     *   - `'inferred'` — the AI inferred this output (e.g. a Vision
     *     statement synthesised from public materials rather than
     *     extracted from a stated source). Maps to backend's
     *     `synthesised: true`.
     *
     * Forward-compatible: future kinds (`'extracted'`, `'from-upload'`,
     * `'from-scrape'`) can be added when the backend gains a richer
     * provenance schema; the component's API stays the same.
     */
    kind: 'inferred'
    /**
     * Optional override for the visible label. Defaults to a sensible
     * value per `kind` (e.g., "Inferred"). Useful when a caller wants
     * a tighter or more specific label in a particular context.
     */
    label?: string
}

/**
 * Visual marker for AI-output provenance — communicates "this is
 * AI-inferred" (vs extracted from a real source) without burying the
 * signal in inline parenthetical text.
 *
 * Replaces three different inline-styled `(synthesised)` /
 * `(inferred)` parenthetical patterns scattered across
 * `StrategyMapHeader`, `CoreValuesStrip`, and the print path. One
 * styled component, one accessible name, one icon.
 *
 * Accessibility: the wrapper carries `aria-label="AI-inferred"` (or
 * the per-kind equivalent) so screen-reader users hear a clear
 * provenance phrase. The icon is `aria-hidden`.
 *
 * Visual styling lives in `globals.css` (`.provenance-marker` and
 * `.provenance-marker-icon` classes) so future redesigns of the
 * marker's appearance are a one-place CSS edit.
 *
 * Renders cleanly in both screen and print contexts (no
 * browser-only APIs, no animations).
 */
export default function ProvenanceMarker({ kind, label }: ProvenanceMarkerProps) {
    const config = PROVENANCE_CONFIG[kind]
    const visibleLabel = label ?? config.label
    return (
        <span className="provenance-marker" aria-label={config.ariaLabel} title={config.tooltip}>
            <SparkleIcon />
            {visibleLabel}
        </span>
    )
}

/**
 * Small inline SVG sparkle. Conventional UX shorthand for "AI did this"
 * (used by Anthropic, OpenAI, Google product UIs). Inline so it picks
 * up the parent's `currentColor` and renders identically across
 * platforms (vs an emoji or external icon font).
 */
function SparkleIcon() {
    return (
        <svg className="provenance-marker-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            {/* Four-point star — simple, recognisable, scales clean. */}
            <path d="M12 2 L14 10 L22 12 L14 14 L12 22 L10 14 L2 12 L10 10 Z" />
        </svg>
    )
}

const PROVENANCE_CONFIG: Record<
    ProvenanceMarkerProps['kind'],
    { label: string; ariaLabel: string; tooltip: string }
> = {
    inferred: {
        label: 'Inferred',
        ariaLabel: 'AI-inferred',
        tooltip:
            'AI synthesised this from public materials and pattern-matching, not extracted from a stated source.',
    },
}
