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

The DocumentUpload section header SHALL communicate that uploading documents improves the analysis (rather than being a passive document store). The user-facing section title SHALL be one of: "Improve This Analysis", "Re-analyse with Context", or an equivalent phrasing that explicitly signals improvement intent.

#### Scenario: Section header signals improvement, not document storage

- **WHEN** the page loads
- **THEN** the DocumentUpload section's heading contains language that frames the section as improvement (e.g., "Improve", "Re-analyse with Context", "Refine") rather than a passive label like "Documents" alone

### Requirement: Section markers enable order-based testing

Each top-level section in `AnalysisDetail` SHALL be wrapped at the page level by an element carrying a stable `data-testid` of the form `analysis-section-{name}`, so section ordering is assertable via DOM queries without relying on layout coordinates. Wrapping at the page level (rather than inside each child component) keeps section naming a page concern and preserves any existing component-internal testids (e.g., `strategy-map-view`, `strategy-map-cta`) without test churn.

#### Scenario: Each rendered section is wrapped with an analysis-section testid

- **WHEN** the page is rendered
- **THEN** each of AnalysisHeader, AnalysisExecutiveStrap, AnalysisOverviewCards, TopActionsCallout, StrategyMapView, DeepDiveCTA, EbitdaSection, ValueChainDiagram, RiskBreakdown, ValueLeverSummary, OpportunitiesList, Sc0redCTABanner, and DocumentUpload — when present — is wrapped in an element with a `data-testid` matching the pattern `analysis-section-*` identifying that section
