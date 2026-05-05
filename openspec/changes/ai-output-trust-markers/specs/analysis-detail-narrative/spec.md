## ADDED Requirements

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
