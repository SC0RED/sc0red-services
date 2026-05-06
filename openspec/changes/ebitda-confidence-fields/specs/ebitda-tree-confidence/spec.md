## ADDED Requirements

### Requirement: EBITDA tree nodes carry derivation provenance

Each leaf `EbitdaNode` produced by `build_programmatic_ebitda_tree` SHALL carry two optional fields:

- `confidence_level: Literal["high", "medium", "low"] | None`
- `confidence_basis: str | None` — a 1–2 sentence human-readable explanation of how the node's `value_range` was derived.

Both fields default to `None` for nodes that do not have a deterministic provenance signal (e.g., rollup/subtotal nodes that aggregate children, or nodes produced by a code path that predates this change).

#### Scenario: Revenue node anchored to declared figure tagged high

- **WHEN** `build_programmatic_ebitda_tree` produces a revenue node from a `CompanyProfile` whose declared revenue field is populated
- **THEN** the node's `confidence_level` is `"high"` and `confidence_basis` describes the source (e.g., "Anchored to declared revenue from company profile")

#### Scenario: Revenue node inferred from company-size benchmark tagged medium

- **WHEN** `build_programmatic_ebitda_tree` produces a revenue node from a `CompanyProfile` whose declared revenue is absent but `company_size` resolves via `_SIZE_TO_EMPLOYEES` and the template's `revenue_per_employee`
- **THEN** the node's `confidence_level` is `"medium"` and `confidence_basis` references the inputs (e.g., "Inferred from company-size bracket × industry-benchmark revenue per employee")

#### Scenario: Revenue node defaulted from size bracket tagged low

- **WHEN** `build_programmatic_ebitda_tree` produces a revenue node from a `CompanyProfile` whose `company_size` is absent and `_DEFAULT_EMPLOYEES` is used
- **THEN** the node's `confidence_level` is `"low"` and `confidence_basis` indicates the default fallback (e.g., "Defaulted from generic mid-market size bracket — no company-size signal available")

#### Scenario: Cost node tagged from industry-benchmark margin

- **WHEN** `build_programmatic_ebitda_tree` produces a cost node whose value derives from the template's `gross_margin` or `ebitda_margin`
- **THEN** the node's `confidence_level` reflects the highest confidence among inputs that drove it (revenue base + industry benchmark) and `confidence_basis` references both (e.g., "Inferred from industry-benchmark gross margin applied to estimated revenue")

#### Scenario: Rollup nodes do not carry their own confidence

- **WHEN** `build_programmatic_ebitda_tree` produces a `subtotal` or `margin` node whose value is computed from its children
- **THEN** the node's `confidence_level` is `None` and `confidence_basis` is `None` (the children carry the signal individually; rollups inherit visually via their children's chips)

### Requirement: EbitdaTreeResult schema is additive and backward-compatible

The `EbitdaTreeResult` JSON schema SHALL accept records without the new fields and SHALL surface them as `None` when read back. Existing analyses stored in DynamoDB SHALL deserialize without error.

#### Scenario: Old record deserializes with null confidence

- **WHEN** an `EbitdaTreeResult` record stored before this change is fetched from DynamoDB and parsed
- **THEN** every node's `confidence_level` and `confidence_basis` are `None`; no `ValidationError` is raised

### Requirement: Frontend renders a confidence chip on each leaf node

`EbitdaNodeComponent` SHALL render a chip next to the node's `value_range` when `confidenceLevel` is non-null. The chip SHALL use the existing `ConfidenceIndicator` 3-dot scale: `high → 3 dots`, `medium → 2 dots`, `low → 1 dot`. When `confidenceLevel` is `null`, the chip SHALL NOT render — no fallback "unknown" badge.

#### Scenario: High-confidence node renders 3-dot chip

- **WHEN** an `EbitdaNode` is rendered with `confidenceLevel: "high"` and `value_range: "$10M-$15M"`
- **THEN** the rendered DOM contains a `ConfidenceIndicator` with 3 filled dots adjacent to the value range

#### Scenario: Null confidence suppresses chip

- **WHEN** an `EbitdaNode` is rendered with `confidenceLevel: null`
- **THEN** no `ConfidenceIndicator` is present for that node; no "unknown" / "—" / question-mark badge appears

#### Scenario: Subtotal nodes render no chip

- **WHEN** an `EbitdaNode` of `type: "subtotal"` or `type: "margin"` is rendered
- **THEN** no `ConfidenceIndicator` is present for that node (rollups carry no own confidence per the backend contract)

### Requirement: Hover or focus on the chip reveals the basis tooltip

The confidence chip SHALL expose `confidenceBasis` via the existing `HelpTooltip` primitive — keyboard-focusable, pointer-hover, and tap-on-touch, with `role="tooltip"` and `aria-describedby` association on the trigger.

#### Scenario: Keyboard user reveals the basis

- **WHEN** the user Tabs to a confidence chip and presses Enter or Space
- **THEN** the tooltip becomes visible, displaying the `confidenceBasis` text; the chip trigger has `aria-expanded="true"` (or equivalent state attribute used elsewhere in the page)

#### Scenario: Pointer hover reveals the basis

- **WHEN** the user hovers a confidence chip with a pointer device
- **THEN** the tooltip appears with `confidenceBasis` text after the same delay used by other `HelpTooltip` instances on the page

#### Scenario: Touch tap toggles the basis

- **WHEN** a touch-device user taps a confidence chip
- **THEN** the tooltip appears; tapping outside dismisses it

### Requirement: EBITDA tree legend documents confidence levels

`EbitdaTree` SHALL include a small legend (visible by default, near the tree) defining what each confidence level means. The legend SHALL state plainly that the levels reflect *derivation provenance*, not subjective quality.

#### Scenario: Legend is present on the tree

- **WHEN** an analysis renders an EBITDA tree
- **THEN** the legend is visible and contains explanations roughly matching: "High = anchored to declared data on the company profile / Medium = inferred from company size + industry benchmark / Low = defaulted from a size bracket without company-specific signal"

### Requirement: Print export includes confidence inline

`PrintEbitdaOutline` SHALL render the confidence level inline as plain text (e.g., `(high)`, `(medium)`, `(low)`) appended to each leaf node's value range when `confidenceLevel` is non-null. When `confidenceLevel` is `null`, no marker SHALL render — silence over an "unknown" placeholder.

#### Scenario: PDF print of high-confidence node

- **WHEN** a node with `confidenceLevel: "high"` and `value_range: "$10M-$15M"` is rendered by `PrintEbitdaOutline`
- **THEN** the rendered text contains the value range and the marker `(high)` (or visually equivalent format) in a single readable line

#### Scenario: PDF print of null-confidence node

- **WHEN** a node with `confidenceLevel: null` is rendered by `PrintEbitdaOutline`
- **THEN** the rendered text contains the value range with no confidence marker
