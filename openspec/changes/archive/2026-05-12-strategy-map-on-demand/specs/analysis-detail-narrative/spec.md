## MODIFIED Requirements

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

## ADDED Requirements

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

## REMOVED Requirements

### Requirement: Sc0redCTABanner conditional render after OpportunitiesList

**Reason**: replaced by the repositioned banner at Beat 4. The post-OpportunitiesList position no longer exists in the layout.

**Migration**: the banner component is unchanged structurally — only its render position in `AnalysisDetail.tsx` and the headline / body copy are updated. Existing analytics events keep firing identically.
