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
     * include lightweight inline content like a count badge inside the
     * heading text node itself (e.g. `"AI Opportunities (3)"`).
     *
     * For interactive trailing content like a help-tooltip button, use
     * `titleAdornment` instead — it renders as a SIBLING of the `<h2>`
     * so the heading's accessible name stays exactly the title text.
     */
    title?: ReactNode
    /**
     * Optional inline-trailing content that visually accompanies the
     * heading — typically a `<HelpTooltip>` button, a status indicator,
     * or a small badge. Rendered as a SIBLING of the `<h2>` (NOT inside
     * it) so:
     *
     *   - The `<h2>`'s computed accessible name stays exactly the title
     *     text — screen readers don't concatenate the adornment's
     *     `aria-label` (e.g. "What is EBITDA Tree?") into the heading.
     *   - The adornment is independently focusable and announceable.
     *
     * **Valid uses**: `<HelpTooltip>`, count badges (when not part of the
     * title text), inline status pills, "(synthesised)" markers.
     *
     * **Anti-pattern**: primary action buttons (form submits, navigation
     * links). Those belong in the section body or a dedicated CTA — putting
     * a primary action next to the heading competes for visual focus with
     * the title and breaks the reader's mental model of "heading = label,
     * body = content".
     */
    titleAdornment?: ReactNode
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
 *      every section that has a heading. When a `titleAdornment`
 *      is also present, heading and adornment render as flex
 *      siblings inside a `.section-header-row` container so the
 *      heading's accessible name stays clean.
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
export default function AnalysisSection({ id, title, titleAdornment, lead, children }: AnalysisSectionProps) {
    // Use loose-equality `!= null` (catches both `undefined` AND `null`)
    // so a caller passing `title={null}` doesn't render an empty `<h2>`.
    // ReactNode permits null, so the wider check is the correct contract
    // even if no caller does it today — defends against contract drift.
    const hasHeadingRow = title != null || titleAdornment != null
    return (
        <div data-testid={`analysis-section-${id}`}>
            {hasHeadingRow && (
                <div className="section-header-row">
                    {title != null && <h2 className="section-header">{title}</h2>}
                    {titleAdornment != null && (
                        <span className="section-header-adornment">{titleAdornment}</span>
                    )}
                </div>
            )}
            {lead != null && <p className="section-lead">{lead}</p>}
            {children}
        </div>
    )
}
