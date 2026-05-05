## MODIFIED Requirements

### Requirement: Section markers enable order-based testing

Each top-level section in `AnalysisDetail` SHALL be wrapped at the page level by the shared `AnalysisSection` component, which carries a stable `data-testid` of the form `analysis-section-{name}`, so section ordering is assertable via DOM queries without relying on layout coordinates. Wrapping at the page level (rather than inside each child component) keeps section naming a page concern and preserves any existing component-internal testids (e.g., `strategy-map-view`, `strategy-map-cta`, `drop-zone`, `reanalyze-progress`, `ebitda-tree`) without test churn.

The `AnalysisSection` component SHALL also own the section's *visual framing* — heading and optional lead paragraph — so framing is consistent across every section that has a heading. Sections that do not have a section-level heading by design (StrategyMapView, Sc0redCTABanner, DeepDiveCTA, TopActionsCallout, AnalysisOverviewCards, AnalysisExecutiveStrap, AnalysisHeader) MAY be wrapped by `AnalysisSection` without a `title` prop — in that case, only the testid is rendered, no visible heading.

#### Scenario: Each rendered section is wrapped with an analysis-section testid

- **WHEN** the page is rendered
- **THEN** each of AnalysisHeader, AnalysisExecutiveStrap, AnalysisOverviewCards, TopActionsCallout, StrategyMapView, DeepDiveCTA, EbitdaSection, ValueChainDiagram, RiskBreakdown, ValueLeverSummary, OpportunitiesList, Sc0redCTABanner, and DocumentUpload — when present — is wrapped in an element with a `data-testid` matching the pattern `analysis-section-*` identifying that section

#### Scenario: Page-level wrapping uses the shared AnalysisSection component

- **WHEN** the page is rendered
- **THEN** every wrapping element with a `data-testid` matching `analysis-section-*` is produced by the `AnalysisSection` component (not by an inline helper or one-off `<div>`)

### Requirement: DocumentUpload section is framed as analysis improvement

The DocumentUpload section header SHALL communicate that uploading documents improves the analysis (rather than being a passive document store). The user-facing section title SHALL be one of: "Improve This Analysis", "Re-analyse with Context", or an equivalent phrasing that explicitly signals improvement intent. The title SHALL be rendered through the page-level `AnalysisSection` wrapper, not inline inside `DocumentUpload`.

#### Scenario: Section header signals improvement, not document storage

- **WHEN** the page loads
- **THEN** the DocumentUpload section's heading contains language that frames the section as improvement (e.g., "Improve", "Re-analyse with Context", "Refine") rather than a passive label like "Documents" alone

#### Scenario: DocumentUpload framing is rendered through AnalysisSection

- **WHEN** the page loads
- **THEN** the "Improve This Analysis" heading + lead paragraph are rendered as the `title` and `lead` props of the `AnalysisSection` wrapper around `DocumentUpload`, NOT as inline JSX adjacent to it

## ADDED Requirements

### Requirement: Section headings render with one consistent visual treatment

Every section-level heading on the analysis detail page SHALL render through a single visual treatment (the `.section-header` CSS class, applied by the shared `AnalysisSection` component). Inline-styled equivalents (e.g., `<h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem' }}>`) SHALL NOT be used.

The following sections render their heading via `AnalysisSection`'s `title` prop and the page level — NOT internally:

- RiskBreakdown ("Risk Breakdown")
- EbitdaSection ("EBITDA Impact Model")
- ValueChainDiagram ("Value Chain Analysis")
- ValueLeverSummary ("Value Impact")
- OpportunitiesList ("AI Opportunities ({count})")
- DocumentUpload ("Improve This Analysis")

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

### Requirement: AnalysisSection component owns the page-level framing contract

A shared `AnalysisSection` React component SHALL exist at a stable import path (`@/components/analysis/AnalysisSection`) and SHALL be the single component used to wrap top-level sections of the analysis detail page. The component's prop contract:

- `id: string` — required; produces `data-testid="analysis-section-{id}"` on the wrapper element
- `title?: ReactNode` — optional; when provided, rendered as `<h2 className="section-header">` inside the wrapper above the children
- `lead?: ReactNode` — optional; when provided, rendered as a paragraph below the title and above the children, in the established secondary-text style
- `children: ReactNode` — required; the section's body content

The component SHALL NOT introduce any side effects, state, or hooks.

#### Scenario: Wrapper renders only the testid when title and lead are absent

- **WHEN** `AnalysisSection` is rendered with only `id` and `children`
- **THEN** the rendered DOM contains a single wrapping element with `data-testid="analysis-section-{id}"` and the children, with no `<h2>` and no lead paragraph

#### Scenario: Wrapper renders the title as an h2 with the section-header class

- **WHEN** `AnalysisSection` is rendered with a string `title`
- **THEN** the rendered DOM contains an `<h2>` element bearing the `section-header` CSS class with the title text as its content

#### Scenario: Wrapper accepts a ReactNode title for adornments

- **WHEN** `AnalysisSection` is rendered with a `title` that is a React fragment containing both text and an adornment component (e.g., a `HelpTooltip`)
- **THEN** the rendered DOM contains the title text AND the adornment component's output inside the `<h2>`

#### Scenario: Wrapper renders the lead paragraph below the title

- **WHEN** `AnalysisSection` is rendered with both `title` and `lead`
- **THEN** the rendered DOM contains the title `<h2>` followed by a `<p>` containing the lead content, both above the children

#### Scenario: Wrapper produces the testid attribute regardless of title/lead presence

- **WHEN** `AnalysisSection` is rendered with `id="ebitda"` and any combination of title/lead
- **THEN** the wrapping element carries `data-testid="analysis-section-ebitda"`
