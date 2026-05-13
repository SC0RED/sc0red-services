## MODIFIED Requirements

### Requirement: Section render order on the analysis detail page

The analysis-detail page SHALL render its sections in the following beat order:

- **Beat 1** — Hero (company name, risk tier, identity).
- **Beat 2** — Top 3 Immediate Actions.
- **Beat 3** — Strategy Map.
- **Beat 4** — `Sc0redCTABanner` "Want a deeper analysis?" rendered in its EXPANDED state by default (not the compact collapsed banner). It MUST remain user-dismissible (collapse / hide).
- **Beat 5** — EBITDA tree.
- **Beat 6** — Opportunities list.
- **Beat 7** — Risk profile + risk scores.
- **Beat 8** — Value chain (if present).

Beat 3 renders the strategy map as a first-class, always-present artifact for analyses created after the `redesign-strategy-map` change. The DeepDiveCTA component previously rendered below the strategy map at the old Beat 6 position is removed.

#### Scenario: Standard render order on a fresh analysis

- **WHEN** an analysis-detail page loads for an analysis with all sections populated
- **THEN** the page renders the sections in the order above
- **AND** the strategy map appears at Beat 3, immediately after the Top 3 Immediate Actions
- **AND** the Sc0redCTABanner appears at Beat 4, immediately after the strategy map, in its expanded state

#### Scenario: Sc0redCTABanner is dismissible

- **WHEN** the user dismisses (collapses or hides) the Beat 4 Sc0redCTABanner
- **THEN** the banner collapses to its compact state (or hides entirely, per the existing dismiss behaviour)
- **AND** the dismissal is preserved across analysis-detail page navigations within the session (or persistently, matching today's behaviour)

### Requirement: Strategy-map slot renders two states (PRESENT or REGENERATABLE)

The Beat 3 strategy-map slot SHALL render one of two mutually-exclusive states based on the persisted analysis:

- **PRESENT**: the assessment record has a populated `strategyMap` field. Render the 2D canvas (`StrategyMapView`) showing perspectives, chips, and arrows.
- **REGENERATABLE**: the assessment record has no `strategyMap` field (analysis predates this change, or strategy-map generation failed). Render an inline "Regenerate strategy map" affordance — a button that triggers `POST /api/analysis/{id}/strategy-map/regenerate` and, on success, re-renders the slot in the PRESENT state.

The previously-existing GENERATING and ABSENT-with-CTA states are removed. There is no on-demand CTA for new analyses — they always render in PRESENT.

#### Scenario: New analyses always render PRESENT

- **WHEN** an analysis-detail page loads for an analysis with a populated `strategyMap`
- **THEN** the Beat 3 slot renders the 2D canvas (`StrategyMapView`)
- **AND** no "Generate strategy map" CTA is rendered

#### Scenario: Old analyses render the regenerate affordance

- **WHEN** an analysis-detail page loads for an analysis with no `strategyMap` field
- **THEN** the Beat 3 slot renders the "Regenerate strategy map" affordance
- **AND** clicking it sends `POST /api/analysis/{id}/strategy-map/regenerate`
- **AND** on success the slot re-renders in the PRESENT state with the new strategy map

## ADDED Requirements

### Requirement: Sc0redCTABanner supports an expanded-by-default render mode

The `Sc0redCTABanner` component SHALL accept an `expanded` prop (boolean, default `false`). When `expanded={true}` (the Beat 4 mount-site default), the banner renders its FULL value-proposition layout instead of the compact CTA bar. The expanded layout occupies more vertical space and surfaces the deeper-analysis offer prominently. The component continues to be user-dismissible.

Legacy call sites of `Sc0redCTABanner` that did not pass `expanded` continue to render in the compact mode (backward-compatible).

#### Scenario: Banner is expanded at Beat 4

- **WHEN** the analysis-detail page renders the Beat 4 mount site
- **THEN** the `Sc0redCTABanner` renders with `expanded={true}`
- **AND** the rendered DOM shows the full value-proposition layout, not the compact CTA bar

#### Scenario: Other call sites preserve compact rendering

- **WHEN** a non-Beat-4 caller mounts `Sc0redCTABanner` without specifying `expanded`
- **THEN** the banner renders in the compact mode (matching pre-change behaviour)

## REMOVED Requirements

### Requirement: Strategy-map slot renders three distinct states

**Reason**: The on-demand generation model is being removed (see the `ai-strategy-map` capability delta). With pipeline integration, the strategy map is always present (or always regeneratable for legacy analyses). The intermediate GENERATING state is no longer reachable in the user flow. The slot's state machine collapses from three states to two, captured in the MODIFIED requirement above.

**Migration**: the `StrategyMapGeneratingPlaceholder` and `StrategyMapCTA` components are deleted, along with the `useStrategyMapSubscription` hook that drove the AppSync-pushed GENERATING transition. The `DeepDiveCTA` component below the slot is also deleted.
