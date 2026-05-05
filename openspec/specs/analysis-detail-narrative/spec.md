### Requirement: Section render order on the analysis detail page

The analysis detail page (`/analysis/[analysisId]`) SHALL render its sections in the following top-to-bottom order, for any analysis that has completed successfully (i.e., the `FailedAnalysisView` branch is not taken):

1. AnalysisHeader
2. AnalysisExecutiveStrap
3. AnalysisOverviewCards
4. TopActionsCallout
5. StrategyMapView (only when `data.strategyMap` is present)
6. DeepDiveCTA (only when `data.strategyMap` is present)
7. EbitdaSection (only when `data.ebitdaTree` is present)
8. ValueChainDiagram (only when `data.valueChain.steps.length > 0`)
9. RiskBreakdown
10. ValueLeverSummary
11. OpportunitiesList
12. Sc0redCTABanner (only when `data.opportunities.length > 0`)
13. DocumentUpload

Conditional sections that are omitted MUST NOT shift the relative order of the remaining sections.

#### Scenario: Full data renders all 13 sections in the prescribed order

- **WHEN** the analysis page loads with strategy map, ebitda tree, value chain steps, and at least one opportunity
- **THEN** the rendered DOM contains, in order: header, executive strap, overview cards, top actions, strategy map, deep-dive CTA, EBITDA, value chain, risk breakdown, value lever summary, opportunities list, sc0red CTA banner, document upload

#### Scenario: Analysis without a strategy map skips strategy-frame sections but preserves order

- **WHEN** the analysis page loads with `strategyMap === null`
- **THEN** the rendered DOM contains the same sections in the same relative order, with StrategyMapView and DeepDiveCTA absent

#### Scenario: Analysis without an EBITDA tree skips EBITDA but preserves order

- **WHEN** the analysis page loads with `ebitdaTree === null`
- **THEN** EbitdaSection is absent and the section immediately following the strategy-frame beat is ValueChainDiagram (or, if ValueChain is also absent, RiskBreakdown)

#### Scenario: Analysis with zero opportunities omits the Sc0red CTA

- **WHEN** the analysis page loads with `opportunities.length === 0`
- **THEN** Sc0redCTABanner does not render and DocumentUpload follows OpportunitiesList directly

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
