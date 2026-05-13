### Requirement: Section render order on the analysis detail page

The analysis detail page (`/analysis/[analysisId]`) SHALL render its sections in the following top-to-bottom order, for any analysis that has completed successfully (i.e., the `FailedAnalysisView` branch is not taken):

1. AnalysisHeader
2. AnalysisExecutiveStrap
3. AnalysisOverviewCards
4. **Sc0redCTABanner** ← MOVED from position 12 (after OpportunitiesList) to here
5. TopActionsCallout
6. EbitdaSection (only when `data.ebitdaTree` is present)
7. ValueChainDiagram (only when `data.valueChain.steps.length > 0`)
8. RiskBreakdown
9. ValueLeverSummary
10. OpportunitiesList
11. **Strategy-map slot** ← MOVED from positions 5-6 (after TopActionsCallout) to here. Slot has three states:
    - **CTA state**: `<StrategyMapCTA />` rendered when `data.strategyMap` is null/absent AND `data.strategyMapGenerationState` is not `"generating"`.
    - **Generating state**: skeleton placeholder + status message rendered when `data.strategyMapGenerationState === "generating"`.
    - **Present state**: `<StrategyMapView />` followed by `<DeepDiveCTA />` rendered when `data.strategyMap` is populated. DeepDiveCTA renders ONLY in the present state — it pairs with the rendered map.
12. DocumentUpload

Conditional sections that are omitted MUST NOT shift the relative order of the remaining sections.

#### Scenario: Strategy map present, full data renders all sections in the prescribed order

- **WHEN** the analysis page loads with `strategyMap` populated, ebitda tree, value chain steps, and at least one opportunity
- **THEN** the rendered DOM contains, in order: header, executive strap, overview cards, sc0red CTA banner, top actions, EBITDA, value chain, risk breakdown, value lever summary, opportunities list, strategy map view, deep-dive CTA, document upload

#### Scenario: Strategy map absent (CTA state) renders the CTA at Beat 6 position

- **WHEN** the analysis page loads with `strategyMap` null AND `strategyMapGenerationState` not `"generating"`
- **THEN** the rendered DOM contains the StrategyMapCTA at the strategy-map slot position (after OpportunitiesList, before DocumentUpload)
- **AND** StrategyMapView and DeepDiveCTA are absent
- **AND** the surrounding section order is unchanged

#### Scenario: Strategy map generating state renders skeleton placeholder

- **WHEN** the analysis page loads with `strategyMapGenerationState === "generating"`
- **THEN** the rendered DOM contains a skeleton placeholder + status message ("Generating your strategy map...") at the strategy-map slot position
- **AND** StrategyMapCTA is NOT rendered (the user has already clicked)
- **AND** StrategyMapView and DeepDiveCTA are absent

#### Scenario: Sc0redCTABanner renders at Beat 4 position regardless of opportunity count

- **WHEN** the analysis page loads (any analysis state)
- **THEN** the Sc0redCTABanner renders between AnalysisOverviewCards and TopActionsCallout
- **AND** it does NOT render at the post-OpportunitiesList position

#### Scenario: Analysis without an EBITDA tree skips EBITDA but preserves order

- **WHEN** the analysis page loads with `ebitdaTree === null`
- **THEN** EbitdaSection is absent and the section immediately following TopActionsCallout is ValueChainDiagram (or, if ValueChain is also absent, RiskBreakdown)

#### Scenario: DeepDiveCTA renders only when the strategy map is present

- **WHEN** the analysis page loads in the strategy-map CTA or generating state
- **THEN** DeepDiveCTA is absent
- **WHEN** the analysis page loads in the strategy-map present state
- **THEN** DeepDiveCTA renders immediately after StrategyMapView

### Requirement: Strategy-map slot renders three distinct states

The analysis detail page SHALL render exactly one of three states in the strategy-map slot, derived from the `data.strategyMap` and `data.strategyMapGenerationState` fields:

| State | Condition | Rendered components |
|---|---|---|
| CTA | `strategyMap` is null/absent AND `strategyMapGenerationState !== "generating"` | `<StrategyMapCTA />` |
| Generating | `strategyMapGenerationState === "generating"` | skeleton placeholder + status message + AppSync subscription via `useStrategyMapSubscription` hook |
| Present | `strategyMap` is populated | `<StrategyMapView />` followed by `<DeepDiveCTA />` |

The three states are mutually exclusive. The frontend SHALL NOT render the CTA while a generation is in progress (otherwise users could enqueue duplicate jobs by clicking again).

#### Scenario: User clicking the CTA transitions to generating state

- **WHEN** the user clicks "Generate strategy map" in the CTA state
- **THEN** the frontend POSTs to `/api/analysis/{id}/strategy-map`, receives 202 Accepted
- **AND** the slot transitions to the generating state via optimistic UI update (skeleton + status message)
- **AND** the CTA is no longer visible

#### Scenario: AppSync completion event transitions generating → present

- **WHEN** the slot is in generating state and `useStrategyMapSubscription` receives a `strategy_map_complete` event for this analysis
- **THEN** the hook fires `GET /api/analysis/{id}` to fetch the persisted map
- **AND** the slot transitions to the present state on response

#### Scenario: AppSync failure event transitions generating → CTA with error message

- **WHEN** the slot is in generating state and `useStrategyMapSubscription` receives a `strategy_map_failed` event
- **THEN** the slot transitions back to CTA state
- **AND** a "Generation failed — try again" message renders above the CTA button
- **AND** the failure message clears when the user clicks the CTA again

### Requirement: Sc0redCTABanner is repositioned to Beat 4 with reframed copy

The `Sc0redCTABanner` component SHALL render at Beat 4 of the analysis page (after `AnalysisOverviewCards`, before `TopActionsCallout`) — not after `OpportunitiesList`. There SHALL be exactly one banner instance per page.

The collapsed-state headline SHALL be analysis-centric (not opportunity-centric) — final wording is leadership's call but the framing direction is "dig deeper" / advisor support / human eye on the analysis as a whole. The expanded-state body SHALL describe sc0red's PE-experienced advisor offering without referencing "these opportunities" (which haven't been shown yet at this position).

The banner's existing analytics events (`sc0red_cta_banner_expanded`, `sc0red_cta_banner_collapsed`, `sc0red_cta_clicked`) SHALL continue to fire identically. The `analyticsContext` payload (`analysisId`, `opportunityCount`, `activeLeverFilter`) SHALL still populate from the loaded analysis data — at the new top position the values represent state from later in the page, but the events are about banner interaction, not opportunity context.

#### Scenario: Banner appears at Beat 4 regardless of analysis state

- **WHEN** any analysis loads (CTA / generating / present strategy-map state, with or without opportunities)
- **THEN** the Sc0redCTABanner is rendered between AnalysisOverviewCards and TopActionsCallout
- **AND** it is NOT rendered at the post-OpportunitiesList position

#### Scenario: Banner copy is analysis-centric, not opportunity-centric

- **WHEN** the banner is in collapsed state
- **THEN** the headline copy does NOT contain the literal phrase "these opportunities" (which forward-references content not yet shown)
- **AND** the headline frames sc0red as advisor / deeper-dive support for the analysis as a whole

#### Scenario: Analytics events fire unchanged

- **WHEN** the user expands, collapses, or clicks through the banner at the new position
- **THEN** the same `sc0red_cta_banner_expanded` / `_collapsed` / `sc0red_cta_clicked` events fire with the existing `analyticsContext` payload
- **AND** the `keepalive: true` semantics on the click event are preserved

### Requirement: Executive strap renders a one-line summary above the overview cards

The page SHALL render an `AnalysisExecutiveStrap` element between `AnalysisHeader` and `AnalysisOverviewCards` for every successful analysis. The strap SHALL be a single visual element that compresses the analysis into a transcribable one-line summary.

The strap SHALL include:
- Company name
- AI risk score (formatted to one decimal place) and risk tier label
- Opportunity count
- Estimated EBITDA range, when an EBITDA tree is present
- Last-analysed date, when present

The EBITDA range and last-analysed segments SHALL be omitted entirely (including their preceding separator) when their source data is absent — they MUST NOT render with placeholder values such as "—" or "N/A".

#### Scenario: Strap renders all five segments when full data is available

- **WHEN** the page loads with non-null `overallRiskScore`, `riskTier`, `opportunities`, `ebitdaTree`, and `analyzedAt`
- **THEN** the strap reads in the form `{companyName} — AI Risk {score} / {tier} · {N} opportunities · est. EBITDA range {low}–{high} · last analysed {date}`

#### Scenario: Strap omits the EBITDA segment when ebitdaEstimate is missing

- **WHEN** the page loads with `ebitdaTree?.ebitdaEstimate` undefined (either because `ebitdaTree` itself is null or because the field is absent from the tree)
- **THEN** the strap reads `{companyName} — AI Risk {score} / {tier} · {N} opportunities · last analysed {date}` with no EBITDA segment and no orphaned separator

#### Scenario: Strap omits the analysed-date segment when analyzedAt is null

- **WHEN** the page loads with `analyzedAt === null` and other fields present
- **THEN** the strap omits the "last analysed" segment and its leading separator

#### Scenario: Strap displays the precomputed top-level EBITDA estimate

- **WHEN** `ebitdaTree.ebitdaEstimate` is a non-empty string
- **THEN** the displayed range is exactly that string (e.g., `$2M-$8M`), with no client-side parsing, leaf-walking, or substitution from `revenueEstimate`

### Requirement: Re-analyse loop has an explicit, labelled control

The DocumentUpload section SHALL expose an explicitly labelled "Re-analyse" button that triggers re-analysis. The button SHALL be reachable by keyboard, have an accessible name, and SHALL be visible whenever at least one document is associated with the analysis.

The implicit-on-upload re-analyse trigger MAY remain in place as an additional convenience path — but it MUST NOT be the only way to start a re-analysis.

#### Scenario: Re-analyse button is visible when documents are present

- **WHEN** the page loads with `documents.length > 0`
- **THEN** a button labelled "Re-analyse" (or equivalent accessible name including the word "re-analyse" or "re-analyze") renders inside the DocumentUpload section

#### Scenario: Re-analyse button is disabled while a re-analysis is running

- **WHEN** `reanalyzing === true`
- **THEN** the Re-analyse button is rendered with a disabled state and clicking it does not trigger a second re-analysis

#### Scenario: Clicking the button triggers the same code path as upload-driven re-analysis

- **WHEN** a user clicks the Re-analyse button while `reanalyzing === false` and at least one document is present
- **THEN** the same `onReanalyze` handler that an upload-triggered re-analysis would invoke is called exactly once

### Requirement: Re-analyse progress is co-located with the affordance that triggers it

While a re-analysis is running, the progress indicator (label + progress bar + percent-complete readout) SHALL render inside the DocumentUpload section, not in a separate sibling block elsewhere on the page.

#### Scenario: Progress indicator renders inside DocumentUpload during re-analysis

- **WHEN** `reanalyzing === true`
- **THEN** the progress indicator's DOM is a descendant of the DocumentUpload section's root element

#### Scenario: No orphaned progress block exists outside DocumentUpload

- **WHEN** the page is rendered in any state
- **THEN** there is no progress indicator rendered as a sibling of DocumentUpload at the top level of `AnalysisDetail`

### Requirement: DocumentUpload section is framed as analysis improvement

The DocumentUpload section header SHALL communicate that uploading documents improves the analysis (rather than being a passive document store). The user-facing section title SHALL be one of: "Improve This Analysis", "Re-analyse with Context", or an equivalent phrasing that explicitly signals improvement intent. The title SHALL be rendered through the page-level `AnalysisSection` wrapper, not inline inside `DocumentUpload`.

#### Scenario: Section header signals improvement, not document storage

- **WHEN** the page loads
- **THEN** the DocumentUpload section's heading contains language that frames the section as improvement (e.g., "Improve", "Re-analyse with Context", "Refine") rather than a passive label like "Documents" alone

#### Scenario: DocumentUpload framing is rendered through AnalysisSection

- **WHEN** the page loads
- **THEN** the "Improve This Analysis" heading + lead paragraph are rendered as the `title` and `lead` props of the `AnalysisSection` wrapper around `DocumentUpload`, NOT as inline JSX adjacent to it

### Requirement: Section markers enable order-based testing

Each top-level section in `AnalysisDetail` SHALL be wrapped at the page level by the shared `AnalysisSection` component, which carries a stable `data-testid` of the form `analysis-section-{name}`, so section ordering is assertable via DOM queries without relying on layout coordinates. Wrapping at the page level (rather than inside each child component) keeps section naming a page concern and preserves any existing component-internal testids (e.g., `strategy-map-view`, `strategy-map-cta`, `drop-zone`, `reanalyze-progress`, `ebitda-tree`) without test churn.

The `AnalysisSection` component SHALL also own the section's *visual framing* — heading and optional lead paragraph — so framing is consistent across every section that has a heading. Sections that do not have a section-level heading by design (StrategyMapView, Sc0redCTABanner, DeepDiveCTA, TopActionsCallout, AnalysisOverviewCards, AnalysisExecutiveStrap, AnalysisHeader) MAY be wrapped by `AnalysisSection` without a `title` prop — in that case, only the testid is rendered, no visible heading.

#### Scenario: Each rendered section is wrapped with an analysis-section testid

- **WHEN** the page is rendered
- **THEN** each of AnalysisHeader, AnalysisExecutiveStrap, AnalysisOverviewCards, TopActionsCallout, StrategyMapView, DeepDiveCTA, EbitdaSection, ValueChainDiagram, RiskBreakdown, ValueLeverSummary, OpportunitiesList, Sc0redCTABanner, and DocumentUpload — when present — is wrapped in an element with a `data-testid` matching the pattern `analysis-section-*` identifying that section

#### Scenario: Page-level wrapping uses the shared AnalysisSection component

- **WHEN** the page is rendered
- **THEN** every wrapping element with a `data-testid` matching `analysis-section-*` is produced by the `AnalysisSection` component (not by an inline helper or one-off `<div>`)

### Requirement: Section headings render with one consistent visual treatment

Every section-level heading on the analysis detail page SHALL render through a single visual treatment (the `.section-header` CSS class, applied by the shared `AnalysisSection` component). Inline-styled equivalents (e.g., `<h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem' }}>`) SHALL NOT be used.

The following sections render their heading via `AnalysisSection`'s `title` prop and the page level — NOT internally:

- RiskBreakdown ("Risk Breakdown")
- EbitdaSection ("EBITDA Impact Model")
- ValueChainDiagram ("Value Chain Analysis")
- ValueLeverSummary ("Value Impact")
- OpportunitiesList ("AI Opportunities ({count})")
- DocumentUpload ("Improve This Analysis")

When a section's heading is accompanied by an inline help affordance (a `HelpTooltip`), the help affordance SHALL be passed through `AnalysisSection`'s `titleAdornment` prop — NOT embedded inside the `title` prop as a fragment child of the heading. This ensures the heading's accessible name is the title text alone, free of adornment content.

The following sections are EXEMPT from the consistent-heading rule, each by intentional design:

- **StrategyMapView** — uses a marquee uppercase-blue "STRATEGY MAP" treatment because the strategy map is the page's marquee artifact
- **Sc0redCTABanner**, **DeepDiveCTA** — CTA cards with internal framing that is part of their identity, not page-level sections
- **TopActionsCallout** — a stylized callout card with a pseudo-heading (`<span>Top 3 Immediate Actions</span>`), not a sectioned region
- **AnalysisOverviewCards** — a paired card row (score + radar) with internal labels, no section heading by design
- **AnalysisExecutiveStrap** — a one-line summary band, no heading by design
- **AnalysisHeader** — the page-level heading (`<h1>` company name), not a section heading

The exempt list is closed for v1 — adding new exempt sections requires a follow-up change to the spec.

#### Scenario: All non-exempt sections render their heading via the page-level wrapper

- **WHEN** the page is rendered with full data
- **THEN** for each of RiskBreakdown, EbitdaSection, ValueChainDiagram, ValueLeverSummary, OpportunitiesList, and DocumentUpload, the visible heading text appears in the DOM as a child of the corresponding `AnalysisSection` wrapper (not inside the wrapped component)

#### Scenario: No internal `<h2>` heading is rendered by migrated section components

- **WHEN** any of the migrated components (RiskBreakdown, EbitdaSection, ValueChainDiagram, ValueLeverSummary, OpportunitiesList, DocumentUpload) is rendered in isolation
- **THEN** no `<h2>` element with the section's title text appears inside its rendered output

#### Scenario: Inline-styled section headings are eliminated

- **WHEN** the analysis detail page is rendered
- **THEN** no `<h2>` element with an inline `style` attribute that duplicates the `.section-header` rule (font-size 1.125rem, font-weight 700, margin-bottom 1rem) appears anywhere in the rendered DOM

#### Scenario: Heading accessible name excludes help-tooltip text

- **WHEN** a section heading like "EBITDA Impact Model" is rendered with an accompanying `HelpTooltip` adornment
- **THEN** the `<h2>` element's computed accessible name is exactly `"EBITDA Impact Model"` — the help-tooltip's button `aria-label` (e.g. `"What is EBITDA Tree?"`) is NOT included
- **AND** querying via `getByRole('heading', { name: 'EBITDA Impact Model' })` (exact match) succeeds

### Requirement: AnalysisSection component owns the page-level framing contract

A shared `AnalysisSection` React component SHALL exist at a stable import path (`@/components/analysis/AnalysisSection`) and SHALL be the single component used to wrap top-level sections of the analysis detail page. The component's prop contract:

- `id: string` — required; produces `data-testid="analysis-section-{id}"` on the wrapper element
- `title?: ReactNode` — optional; when provided, rendered as `<h2 className="section-header">` above the children
- `titleAdornment?: ReactNode` — optional; when provided, rendered as a SIBLING of the `<h2>` (NOT a child) inside a flex row, so the heading's accessible name remains exactly the title text and the adornment is independently focusable / announceable. Typical use: a help-tooltip button, a status indicator, or other inline-trailing content that visually accompanies the heading.
- `lead?: ReactNode` — optional; when provided, rendered as a paragraph below the title row and above the children, in the established secondary-text style
- `children: ReactNode` — required; the section's body content

The component SHALL NOT introduce any side effects, state, or hooks.

When both `title` and `titleAdornment` are provided, the heading and adornment SHALL render as flex siblings inside a single row container, NOT with the adornment nested inside the heading element. This structural separation ensures the `<h2>`'s computed accessible name (per the W3C accessible-name algorithm) is exactly the title text.

#### Scenario: Wrapper renders only the testid when title and lead are absent

- **WHEN** `AnalysisSection` is rendered with only `id` and `children`
- **THEN** the rendered DOM contains a single wrapping element with `data-testid="analysis-section-{id}"` and the children, with no `<h2>`, no lead paragraph, and no row wrapper

#### Scenario: Wrapper renders the title as an h2 with the section-header class

- **WHEN** `AnalysisSection` is rendered with a string `title`
- **THEN** the rendered DOM contains an `<h2>` element bearing the `section-header` CSS class with the title text as its content

#### Scenario: Wrapper accepts a ReactNode title for adornments

- **WHEN** `AnalysisSection` is rendered with a `title` that is a React fragment containing both text and an adornment component (e.g., a count badge)
- **THEN** the rendered DOM contains the title text AND the adornment component's output inside the `<h2>`

#### Scenario: titleAdornment renders as a sibling of the h2, not a child

- **WHEN** `AnalysisSection` is rendered with both a `title` and a `titleAdornment` (e.g. a `HelpTooltip`)
- **THEN** the rendered DOM contains the `<h2>` and the adornment as siblings inside a row container; the adornment's elements are NOT descendants of the `<h2>`
- **AND** the `<h2>`'s computed accessible name is exactly the title text, with no concatenation of the adornment's button labels or contents

#### Scenario: Wrapper renders the lead paragraph below the title row and above the children

- **WHEN** `AnalysisSection` is rendered with `title`, `lead`, and `titleAdornment`
- **THEN** the rendered DOM order is: row container (heading + adornment) → lead `<p>` → children

#### Scenario: Wrapper produces the testid attribute regardless of title/lead/adornment presence

- **WHEN** `AnalysisSection` is rendered with `id="ebitda"` and any combination of title / lead / titleAdornment
- **THEN** the wrapping element carries `data-testid="analysis-section-ebitda"`

### Requirement: AI confidence renders with a dedicated visual encoding distinct from risk-tier color

Every rendering of a `ConfidenceMarker` value (`HIGH | MEDIUM | LOW`) on the analysis detail page SHALL use the `ConfidenceIndicator` component, which renders a dot scale (`●●● / ●●○ / ●○○`) in a single neutral color. The risk-tier color palette (`--risk-low`, `--risk-moderate`, `--risk-high`, `--risk-critical`) SHALL NOT be used for confidence rendering, so that a reader scanning the page never conflates "high confidence" (good) with "low risk" (also good but a different signal).

The component SHALL:
- Render exactly 3 dots, with filled dots = the confidence level (HIGH = 3, MEDIUM = 2, LOW = 1) and the remaining dots rendered hollow
- Use a single neutral color (no green/amber/red palette) for all filled dots
- Provide an accessible name reflecting the level (e.g. `aria-label="Confidence: high"`) so screen-reader users hear the level, not the dot count
- Optionally accept a `size` prop with at least `'small'` and `'default'` variants — `small` for inline contexts (chip headers); `default` for tooltip bodies

The previous `ConfidenceChip` component SHALL be deleted after all consumers migrate.

#### Scenario: HIGH confidence renders 3 filled dots

- **WHEN** the indicator is rendered with `confidence="HIGH"`
- **THEN** 3 filled dots and 0 hollow dots are present
- **AND** the accessible name is "Confidence: high" (case-insensitive match on the level word)

#### Scenario: MEDIUM confidence renders 2 filled + 1 hollow

- **WHEN** the indicator is rendered with `confidence="MEDIUM"`
- **THEN** 2 filled dots and 1 hollow dot are present
- **AND** the accessible name conveys "medium"

#### Scenario: LOW confidence renders 1 filled + 2 hollow

- **WHEN** the indicator is rendered with `confidence="LOW"`
- **THEN** 1 filled dot and 2 hollow dots are present
- **AND** the accessible name conveys "low"

#### Scenario: Risk-tier palette is NOT used for confidence rendering

- **WHEN** the indicator is rendered for any confidence level
- **THEN** the rendered DOM does NOT use any of the CSS variables `--risk-low`, `--risk-moderate`, `--risk-high`, `--risk-critical`, `--risk-low-bg`, `--risk-moderate-bg`, `--risk-high-bg`, `--risk-critical-bg`

#### Scenario: Strategy map node confidence uses the new indicator in both header and tooltip

- **WHEN** a strategy-map node renders an objective with a `confidence` value
- **THEN** the confidence renders via `ConfidenceIndicator` in both the chip's compact header (small size variant) and the tooltip body (default size variant)
- **AND** the legacy `ConfidenceChip` component is no longer present in the rendered DOM

### Requirement: AI provenance renders through a single styled marker component

Every rendering of a `synthesised: boolean` flag on the analysis detail page SHALL use the `ProvenanceMarker` component when the flag is `true`. The component SHALL replace the previously inline-styled `(synthesised)` and `(inferred)` parenthetical text patterns scattered across `StrategyMapHeader`, `CoreValuesStrip`, and the print path.

The component SHALL:
- Accept a `kind` discriminator with at least the value `'inferred'` (covering `synthesised: true` from the backend)
- Render a small inline element with an icon + label (e.g., a sparkle/star SVG + the text "Inferred" in uppercase tertiary styling)
- Provide an accessible name that conveys "AI-inferred" (or equivalent) — the icon is `aria-hidden`, and the wrapper carries an explicit `aria-label`
- Be forward-compatible with future kinds (`'extracted'`, `'from-upload'`, etc.) the backend may add later — additional kinds can be introduced without breaking the existing API

When `synthesised: false`, no marker SHALL render (matches existing behavior).

#### Scenario: Vision rendered with synthesised:true shows a provenance marker

- **WHEN** the strategy-map header renders a Vision with `synthesised: true`
- **THEN** the rendered DOM contains a `ProvenanceMarker` with `kind="inferred"` next to the Vision text
- **AND** the marker's accessible name conveys "AI-inferred" or equivalent
- **AND** no inline `(synthesised)` text remains on the page

#### Scenario: Mission rendered with synthesised:false shows no marker

- **WHEN** the strategy-map header renders a Mission with `synthesised: false`
- **THEN** no `ProvenanceMarker` is rendered next to the Mission heading
- **AND** the Mission text contains no `(synthesised)` parenthetical

#### Scenario: CoreValues marker uses the same component

- **WHEN** the core-values strip renders with `synthesised: true`
- **THEN** the rendered DOM contains a `ProvenanceMarker` with `kind="inferred"` adjacent to the values list
- **AND** no inline `(inferred)` parenthetical text appears separately

#### Scenario: Print path uses the same component

- **WHEN** the print version of the strategy map renders Vision, Mission, or CoreValues with `synthesised: true`
- **THEN** the same `ProvenanceMarker` component is used (not a separate print-only inline-styled span)

#### Scenario: Marker icon is aria-hidden

- **WHEN** any `ProvenanceMarker` renders
- **THEN** the icon element carries `aria-hidden="true"` so screen readers do not announce the SVG path data — the wrapper's `aria-label` is the announceable name

### Requirement: Card-density variants govern analysis-detail-page card surfaces

Every `.card` element rendered on the analysis detail page SHALL apply exactly one of three opinionated density variants (`.card--metric`, `.card--list`, `.card--rich`) alongside the base `.card` class. Each variant locks padding (and may extend to other density rules in future iterations) so the page reads with consistent vertical and horizontal spacing across card surfaces.

The variants are:

- **`.card--metric`** — sparse, single-number / single-badge / single-graphic cards. Generous padding. Used for stat cards.
- **`.card--list`** — compact single-line list rows, often inside expandable accordions. Tight padding. Used for risk rows, opportunity rows, value-chain steps, document list rows.
- **`.card--rich`** — multi-element cards with comfortable internal spacing. Medium padding. Used for radar wrappers, paired stat groups, callout cards with multiple lines.

Inline `padding` styles on `.card` elements within the analysis-detail-page SHALL NOT be used — the variant's locked padding is the source of truth. Inline padding overrides via `style={{ padding: '...' }}` defeat the purpose of the variant system and must be removed during migration.

The bare `.card` class SHALL continue to work (no breaking change) for non-analysis-detail consumers; the variant requirement is scoped to the analysis-detail page.

**Deferred exceptions** (button-cards): three analysis-detail-page consumers — `RiskBreakdown`, `OpportunitiesList`, `ValueChainDiagram` — render an outer `.card` with `style={{ overflow: 'hidden' }}` only (no padding) because an inner `<button>` owns the click + padding semantics. Adding a `card--*` variant to those would stack two padding layers and produce a visual regression. These three consumers are explicitly deferred to the future `ExpandableCard` proposal (UX queue item A), which will introduce the canonical button-card pattern. Until that ships, these three consumers are EXEMPT from the "every card applies a variant" requirement.

#### Scenario: Every non-exempt card on the analysis-detail page applies a variant

- **WHEN** the analysis detail page is rendered with full data
- **THEN** every element with the `card` class within the page — EXCEPT the three deferred button-card consumers (`RiskBreakdown`, `OpportunitiesList`, `ValueChainDiagram`) — also has exactly one of `card--metric`, `card--list`, or `card--rich` in its className
- **AND** no element with the `card` class on the page has an inline `padding` style

#### Scenario: Bare `.card` continues to work for non-analysis-detail consumers

- **WHEN** a component outside the analysis-detail page (e.g., AnalysesTable, ComparisonView, EmptyState) renders an element with the `card` class
- **THEN** the element renders correctly without applying any variant — no visual regression from the variant introduction

#### Scenario: Inline padding alongside a variant is a CONTRACT VIOLATION (not a system-prevented case)

- **WHEN** an element has both `className="card card--list"` and an inline `style={{ padding: '4rem' }}` (a contributor mistake)
- **THEN** the inline `padding` wins over the variant's CSS rule — inline `style` has specificity (1,0,0,0) which is unconditionally higher than any class-only selector (0,2,0)
- **AND** this is a violation of the requirement's primary rule (no inline `padding` styles on `.card` elements within the analysis-detail page); enforcement is by code review and the migration discipline documented in `globals.css`, NOT by CSS specificity
- **NOTE**: a previous draft of this scenario claimed the compound selector "wins via higher specificity" — that claim is factually incorrect for inline styles. The compound selector's actual purpose is to require BOTH the base `.card` AND the variant class to apply (so a typo like `card-metric` silently no-ops), not to override inline styles.

#### Scenario: Picker rule is documented for future contributors

- **WHEN** a developer reads `globals.css` to understand the variants
- **THEN** a comment block at the top of the variant section names each variant and lists when to use it (single-number / list-row / multi-element), so the choice is made by intent rather than by visual eyeballing

### Requirement: Click-to-reveal-detail surfaces use the shared ExpandableCard component

Every "click-to-reveal-detail" interaction surface on the analysis-detail page SHALL render through a shared `ExpandableCard` component (`@/components/ui/ExpandableCard`), which encapsulates the button-card-with-chevron pattern. Specifically:

- `RiskBreakdown` per-risk cards (×8)
- `OpportunitiesList` per-opportunity cards (×5)

**Deferred exceptions** (different visual model, not just different padding):

1. **`ValueChainDiagram` per-step cards (×8)** — horizontal Porter's-value-chain visualization with shared borders, arrow connectors between primary activities, and custom border-radius rules (0 for connected steps, normal for last/support). Migrating to ExpandableCard would replace the chain visual with a vertical list and lose the structural metaphor of sequential primary + parallel support activities. Deferred to a future `value-chain-step-redesign` proposal.

2. **`WhatsMissingPanel` per-gap rows (×4)** — uses `bg-surface-2` + 3px accent-blue left border, NOT the `.card` glassmorphism surface. The accent-strip aesthetic is part of the gaps' visual identity ("here are deep-dive prompts, distinct from regular content"). Migrating to ExpandableCard's `.card.card--list` surface would replace the accent-strip with a glass-card and dilute that identity. Same interaction pattern; different chrome. Deferred to a future `whats-missing-panel-style-alignment` proposal (or absorbed into the `value-chain-step-redesign` follow-up if scope allows).

The interaction pattern (single-open accordion via parent state, ▼ chevron, body reveal) is correct for both deferred consumers; only the visual model differs from `.card.card--list`.

The component SHALL:

- Wrap content in a `.card.card--list` surface (the `card-density-variants` variant from PR #254), with `overflow: hidden` to clip the rounded corners around the body reveal.
- Render exactly one chevron, positioned at the top-right of the header row, in a single glyph (▼ rotating to ▲ on open via CSS `transform: rotate(180deg)` keyed by a `data-open` attribute on the chevron element).
- Use a single motion duration (`0.2s ease`) for the chevron rotation, honoring `prefers-reduced-motion: reduce` via the existing global stylesheet rule.
- Expose ARIA-correct semantics: `aria-expanded` on the trigger `<button>`, `aria-controls` referencing the body's stable id, focus-visible ring on the trigger.
- Support both **controlled** mode (parent passes `isOpen` + `onToggle` for accordion coordination) and **uncontrolled** mode (component owns `useState(false)` internally). Detection is `isOpen !== undefined`.
- Always render the body in the DOM (`hidden` attribute when closed, not conditional rendering) so `aria-controls` always references a valid element.

The strategy-map header's `<details>/<summary>` accordion (`StrategyMapHeader`) is EXEMPT — it uses a different primitive (native `<details>` controlled by parent state) and is intentionally not migrated. Chevron-glyph alignment between `<details>` and `ExpandableCard` is a separate CSS-only follow-up not blocking this requirement.

The 3 button-card consumers previously deferred from `card-density-variants` (RiskBreakdown, OpportunitiesList, ValueChainDiagram) are migrated through `ExpandableCard` in this proposal, completing the card-density consistency rollout.

#### Scenario: Each migrated surface renders through ExpandableCard

- **WHEN** the analysis-detail page renders with full data
- **THEN** every Risk card, Opportunity card, Value-chain step, and What's-Missing gap is rendered as an `ExpandableCard` component (importable from `@/components/ui/ExpandableCard`)
- **AND** none of those surfaces renders an inline `<button aria-expanded>` + chevron pattern outside of `ExpandableCard`'s internals

#### Scenario: Single chevron glyph + position across all migrated surfaces

- **WHEN** any of the migrated cards is rendered (open or closed)
- **THEN** exactly one chevron renders, positioned at the top-right of the header row
- **AND** the chevron is the same SVG element across all migrated surfaces (rendered by `ExpandableCard`'s internal `Chevron` element, not per-consumer inline SVGs)
- **AND** the chevron rotates 180° via CSS transform when the card is in the open state, with `0.2s ease` transition

#### Scenario: Controlled mode coordinates accordion semantics

- **WHEN** an `ExpandableCard` is rendered with both `isOpen={...}` and `onToggle={...}` props
- **THEN** the component uses the parent's `isOpen` value as the source of truth (does NOT manage its own state)
- **AND** clicking the trigger calls `onToggle()` exactly once (parent decides the next state)
- **AND** keyboard activation (Space, Enter) on the trigger has the same effect

#### Scenario: Uncontrolled mode for independent-expand callers

- **WHEN** an `ExpandableCard` is rendered without `isOpen` (or with `isOpen={undefined}`)
- **THEN** the component manages its own open/closed state via `useState(false)`
- **AND** clicking the trigger toggles the internal state — no parent coordination required

#### Scenario: ARIA-correct trigger + body relationship

- **WHEN** an `ExpandableCard` is rendered in any state
- **THEN** the trigger `<button>` has `aria-expanded` set to the current open state (`"true"` or `"false"`)
- **AND** the trigger has `aria-controls` referencing the body's `id`
- **AND** the body element with the matching `id` exists in the DOM regardless of open state (closed cards use the `hidden` HTML attribute, not conditional rendering, so the aria-controls reference is always valid)

### Requirement: Section-to-section vertical spacing is governed by a CSS token

Every section wrapper on the analysis-detail page SHALL apply a consistent inter-section vertical gap via the `--section-margin-bottom` CSS custom property (initial value `2rem`), consumed via the `.analysis-section-spacing` utility class. Inline `marginBottom` styles for section-to-section spacing SHALL NOT be used; the value lives in `:root` and is applied by class.

The token system distinguishes two section-spacing concerns:

- **`--section-gap-y`** (existing, value `1rem`) — INTRA-section vertical gap, used by `.section-header-row` (between heading and adornment row + bottom margin to body) and `.section-lead` (between lead paragraph and body).
- **`--section-margin-bottom`** (NEW, value `2rem`) — INTER-section vertical gap, used by `.analysis-section-spacing` on every section wrapper.

The two tokens are independently named so the picker rule is by intent, not by eyeballing existing examples. Future spacing-related work extends this system rather than introducing parallel token vocabularies.

The following consumers apply `.analysis-section-spacing` to their outer wrapper:

- `RiskBreakdown`
- `OpportunitiesList`
- `ValueChainDiagram`
- `EbitdaSection`
- `DocumentUpload`
- `AnalysisHeader`

The following consumers are EXEMPT (their bottom margin is intentionally non-standard, by design):

- `AnalysisExecutiveStrap` — uses `1.25rem` to pair visually with `AnalysisOverviewCards` beneath it. Documented in the strap's JSDoc.
- `AnalysisOverviewCards` — uses `1.5rem` for the same pairing reason; the score-card + radar row visually clusters with the strap above.

The exempt list is closed for v1 — adding a new exempt section requires a follow-up change to the spec.

#### Scenario: Every non-exempt section wrapper applies the spacing class

- **WHEN** the analysis detail page is rendered with full data
- **THEN** every wrapper for `RiskBreakdown`, `OpportunitiesList`, `ValueChainDiagram`, `EbitdaSection`, `DocumentUpload`, and `AnalysisHeader` carries the `analysis-section-spacing` class
- **AND** none of those wrappers has an inline `marginBottom` style

#### Scenario: Token is consumed via the utility class, not inline

- **WHEN** a developer audits the rendered DOM for inline `style="margin-bottom: 2rem"` on the analysis-detail page
- **THEN** zero matches are found on section outer wrappers (the value comes from the class via the token)

#### Scenario: Picker rule is documented for future contributors

- **WHEN** a developer reads `globals.css` to understand which section-spacing token to use
- **THEN** the comment block at the top of the `:root` declarations names both `--section-gap-y` and `--section-margin-bottom` with one-line descriptions of when to use each (intra-section vs inter-section)

#### Scenario: Exempt sections retain their intentional non-standard spacing

- **WHEN** the analysis detail page is rendered
- **THEN** `AnalysisExecutiveStrap` retains its `1.25rem` bottom margin
- **AND** `AnalysisOverviewCards` retains its `1.5rem` bottom margin
- **AND** the rationale (visual pairing with adjacent elements) is documented in their JSDoc / spec deferred-exceptions list
