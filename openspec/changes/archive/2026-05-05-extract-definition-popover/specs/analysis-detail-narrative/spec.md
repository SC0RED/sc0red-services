## MODIFIED Requirements

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
