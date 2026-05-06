## ADDED Requirements

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
