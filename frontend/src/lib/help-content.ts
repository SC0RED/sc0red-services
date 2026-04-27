/**
 * Single source of truth for the small inline explainers shown next to PE-
 * domain terms in the UI. The `<HelpTooltip term="risk_tier" />` component
 * looks up the matching key here and renders the title + body in a popover.
 *
 * Why a registry (vs inline strings):
 * - These terms appear on multiple surfaces (Analyses, Analysis detail,
 *   Dashboard). One source of truth means edits propagate everywhere.
 * - Copy review is easier: non-engineers can read this one file (or the
 *   mirrored markdown at `docs/help-content.md`) without hunting through
 *   JSX.
 *
 * Editing rules:
 * - Keep `body` to 1-2 sentences. The popover is a quick orientation, not
 *   a glossary entry.
 * - `body` is plain text. No markdown, no HTML. The component renders it
 *   as a `<p>` child.
 * - When you add or rename a key, update `docs/help-content.md` to mirror
 *   the change. The `npm run check:help-content` script (run in CI) will
 *   fail otherwise.
 *
 * See `webapp-ux-foundations-tier2` §2 for the originating spec.
 */

export interface HelpEntry {
    /** Short display title shown in the popover header. */
    title: string
    /** 1-2 sentence plain-text explainer. */
    body: string
}

export const HELP_CONTENT = {
    risk_tier: {
        title: 'Risk Tier',
        body: 'A coarse bucket — Low, Moderate, High, or Critical — derived from the overall risk score. Tiers exist so analysts can scan a portfolio at a glance without reading every score.',
    },
    risk_score: {
        title: 'Risk Score',
        body: 'A 0-10 composite score across multiple risk categories (regulatory, operational, financial, etc). Higher means more risk. The breakdown by category is visible on the analysis detail page.',
    },
    ebitda_tree: {
        title: 'EBITDA Tree',
        body: "A breakdown of the company's earnings drivers — revenue lines minus cost lines, organised so each leaf is an addressable lever. The tree highlights where opportunity and risk concentrate.",
    },
    value_lever: {
        title: 'Value Lever',
        body: 'A specific way to grow the business — either by lifting revenue (Revenue Side) or reducing cost (Cost Side). Each opportunity card is tagged with the lever it pulls.',
    },
    active_lever_filter: {
        title: 'Active Lever Filter',
        body: 'Filter the opportunities list to only show levers on one side of the EBITDA tree. Use this to focus on revenue plays separately from cost plays.',
    },
    industry: {
        title: 'Industry',
        body: "The company's primary industry, classified during the initial scan. Used for benchmarking against peers in the same sector.",
    },
    impact_rating: {
        title: 'Impact Rating',
        body: "A qualitative estimate (Low / Medium / High) of how much an opportunity could move the company's value if executed. Combined with effort to prioritise the playbook.",
    },
} as const satisfies Record<string, HelpEntry>

export type HelpTerm = keyof typeof HELP_CONTENT
