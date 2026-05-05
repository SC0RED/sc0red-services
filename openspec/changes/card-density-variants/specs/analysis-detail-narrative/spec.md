## ADDED Requirements

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
