## MODIFIED Requirements

### Requirement: Section render order on the analysis detail page

The analysis detail page (`/analysis/[analysisId]`) SHALL render its sections in the following top-to-bottom order, for any analysis that has completed successfully (i.e., the `FailedAnalysisView` branch is not taken):

1. AnalysisHeader
2. AnalysisExecutiveStrap
3. AnalysisOverviewCards
4. TopActionsCallout
5. **Strategy-map slot** — three states (see "Strategy-map slot renders three distinct states" requirement below for the state machine). When the map is `present`, this slot also renders the mid-page `DeepDiveCTA` immediately under the table.
6. **Value Proposition & Strategic Priorities** (collapsed `<ExpandableSection>`) — renders when the strategy map is present AND has at least one of `valueProposition.primary` or `strategicPriorities.length >= 1`. See `strategy-map-balanced-scorecard-layout` for the section's internal shape.
7. EbitdaSection (only when `data.ebitdaTree` is present)
8. ValueChainDiagram (only when `data.valueChain.steps.length > 0`)
9. RiskBreakdown
10. ValueLeverSummary
11. OpportunitiesList
12. **QuickWinsMatrix** (Diagnostic Tool Feedback #6) — renders when `opportunities.length >= 1`, omitted otherwise
13. DocumentUpload
14. **DeepDiveCTA (end-of-analysis variant)** — renders on **every successful analysis page**, regardless of opportunity count. The bottom CTA's purpose is "the user reached the end; offer them the next step" — that purpose holds whether or not the analysis surfaced opportunities. Diagnostic Tool Feedback #8.

Conditional sections that are omitted MUST NOT shift the relative order of the remaining sections.

This requirement supersedes the prior section ordering. Specifically:
- The standalone `Sc0redCTABanner` previously at position 4 was removed by the `redesign-strategy-map` Phase 5 change and is no longer rendered anywhere on the analysis page.
- The strategy-map slot's position (post-Phase-5) is between TopActionsCallout and EbitdaSection — moved up from its earlier "after OpportunitiesList" placement.
- The end-of-analysis `DeepDiveCTA` at position 14 was added by Stream A of the Diagnostic Tool Feedback (PR #350). The original implementation gated rendering on `opportunities.length >= 1`; that gate is removed here so the CTA renders on every successful analysis (matches the strategy-map mid-page CTA's gating philosophy: render when the surrounding section is shown).
- The QuickWinsMatrix at position 12 is added by this change.
- The "Value Proposition & Strategic Priorities" expandable at position 6 is added by this change — it relocates content that previously lived inside the strategy-map header (Diagnostic Tool Feedback #4).

#### Scenario: Full-data analysis renders all 14 sections in order

- **WHEN** the analysis page loads with `strategyMap` populated (incl. VP + priorities), `ebitdaTree` populated, `valueChain.steps.length > 0`, and at least one opportunity
- **THEN** the rendered DOM contains, in order: header, strap, overview, top-actions, strategy-map, deep-dive-cta, value-proposition-priorities, ebitda, value-chain, risk-breakdown, value-lever, opportunities, quick-wins-matrix, document-upload, deep-dive-cta-end
- **AND** no element styled as a Sc0redCTABanner is rendered

#### Scenario: Analysis without opportunities omits the matrix but keeps the end-CTA

- **WHEN** the analysis page loads with `opportunities.length === 0` but `strategyMap` populated
- **THEN** the rendered DOM does NOT contain a `quick-wins-matrix` section (the matrix needs opportunities to render)
- **AND** the rendered DOM DOES contain a `deep-dive-cta-end` section (the bottom CTA renders on every successful analysis)
- **AND** the order of the remaining sections is preserved

#### Scenario: Analysis without an EBITDA tree skips EBITDA but preserves order

- **WHEN** the analysis page loads with `data.ebitdaTree` null
- **THEN** the EBITDA section is omitted
- **AND** the surrounding sections (strategy-map slot before, value chain after) preserve their relative order
- **AND** the QuickWinsMatrix still renders after OpportunitiesList when opportunities are present

#### Scenario: Analysis without a strategy map renders no strategy-map slot

- **WHEN** the analysis page loads with `strategyMap` null or absent
- **THEN** the strategy-map slot returns null (no CTA, no skeleton — strategy maps are generated inline during the scan per `redesign-strategy-map` Phase 4)
- **AND** the surrounding section order is preserved

#### Scenario: QuickWinsMatrix is interactive

- **WHEN** the QuickWinsMatrix renders with at least one dot
- **THEN** each dot is keyboard-focusable and exposes its opportunity index
- **AND** clicking or activating a dot publishes a `highlightOpportunities([index])` call via the `OpportunityHoverProvider` (defined in the `analysis-opportunity-overlays` capability spec)

### Requirement: DeepDiveCTA distinguishes placement in analytics

The `DeepDiveCTA` component renders in TWO distinct placements on the analysis page:

- **strategy-map placement** (position 5 in the section order) — under the strategy-map table when the map is present.
- **analysis-end placement** (position 14) — at the bottom of the page on every successful analysis.

Each placement SHALL fire DISTINCT analytics events so the conversion funnel attributes impressions and clicks to the correct surface. The component SHALL accept a `placement: 'strategy-map' | 'analysis-end'` prop that switches:

- The render-event name (`sc0red_cta_rendered_strategy_map` vs `sc0red_cta_rendered_analysis_end`)
- The click-event name (`sc0red_cta_clicked_strategy_map` vs `sc0red_cta_clicked_analysis_end`)
- The outbound URL's `?source=` query parameter (`strategy-map` vs `analysis-end`)

The prior implementation hard-coded `_strategy_map` and `?source=strategy-map` regardless of placement, double-counting the strategy-map funnel by mixing in bottom-CTA impressions and clicks. This requirement fixes that attribution gap.

#### Scenario: Bottom CTA fires analysis-end events

- **WHEN** the analysis page renders the end-of-analysis `DeepDiveCTA` (placement `analysis-end`)
- **THEN** the component fires `sc0red_cta_rendered_analysis_end` on mount with analytics context
- **AND** clicking the CTA fires `sc0red_cta_clicked_analysis_end`
- **AND** the outbound URL contains `?source=analysis-end`

#### Scenario: Mid-page CTA fires strategy-map events

- **WHEN** the analysis page renders the strategy-map `DeepDiveCTA` (placement `strategy-map`)
- **THEN** the component fires `sc0red_cta_rendered_strategy_map` on mount with analytics context
- **AND** clicking the CTA fires `sc0red_cta_clicked_strategy_map`
- **AND** the outbound URL contains `?source=strategy-map`

#### Scenario: Page with both placements fires both events independently

- **WHEN** the analysis page renders both the strategy-map CTA and the end CTA
- **THEN** four distinct analytics events fire over the lifetime of the page: one render per placement, one click per placement (assuming the user clicks each)
- **AND** funnel queries grouped by event name see clean per-placement counts
