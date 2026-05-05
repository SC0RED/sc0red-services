import type { ReactNode } from 'react'

interface AnalysisSectionProps {
    /**
     * Stable id for `data-testid="analysis-section-{id}"`. Required.
     * The page uses this for order-based tests that query wrappers by
     * DOM order rather than relying on layout coordinates.
     */
    id: string
    /**
     * Optional section heading. Rendered as `<h2 className="section-header">`
     * when provided. Accepts `ReactNode` (not just `string`) so callers can
     * include adornments alongside the title — e.g. `<HelpTooltip>` next to
     * "EBITDA Impact Model" or a count badge `({opportunities.length})`
     * next to "AI Opportunities".
     */
    title?: ReactNode
    /**
     * Optional lead paragraph below the heading. Used by sections that
     * need a one-sentence orienting line (e.g. "Improve This Analysis"
     * → "Upload financial statements, board decks, or product docs to
     * refine this analysis"). Omitted by default.
     */
    lead?: ReactNode
    /** Body content of the section. */
    children: ReactNode
}

/**
 * Page-level wrapper for every top-level section on the analysis
 * detail page. Owns three concerns in one component:
 *
 *   1. Stable `data-testid="analysis-section-{id}"` so order-based
 *      tests can query sections by DOM order without coupling to
 *      layout coordinates.
 *   2. Optional heading rendered with the canonical
 *      `.section-header` CSS class — single visual treatment for
 *      every section that has a heading. Replaces the previously-
 *      scattered mix of `<h2 className="section-header">` and
 *      inline-styled `<h2 style={{...}}>` calls across child
 *      components.
 *   3. Optional lead paragraph below the heading, in the established
 *      secondary-text style.
 *
 * All section-level headings on the analysis detail page render
 * through this component. The exempt sections (StrategyMapView,
 * Sc0redCTABanner, DeepDiveCTA, TopActionsCallout, AnalysisOverviewCards,
 * AnalysisExecutiveStrap, AnalysisHeader) render with no `title` prop
 * — they wrap their own internal framing for intentional reasons,
 * documented in `analysis-detail-consistency-wrapper` design D3.
 *
 * Strictly presentational — no state, no hooks, no side effects.
 */
export default function AnalysisSection({ id, title, lead, children }: AnalysisSectionProps) {
    return (
        <div data-testid={`analysis-section-${id}`}>
            {title !== undefined && <h2 className="section-header">{title}</h2>}
            {lead !== undefined && (
                <p
                    style={{
                        margin: '0 0 1rem',
                        fontSize: '0.875rem',
                        color: 'var(--text-secondary)',
                        lineHeight: 1.6,
                    }}
                >
                    {lead}
                </p>
            )}
            {children}
        </div>
    )
}
