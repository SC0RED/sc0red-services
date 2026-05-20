## MODIFIED Requirements

### Requirement: Section render order on the analysis detail page

The analysis detail page (`/analysis/[analysisId]`) SHALL render its sections in the following top-to-bottom order, for any analysis that has completed successfully (i.e., the `FailedAnalysisView` branch is not taken):

1. AnalysisHeader
2. AnalysisExecutiveStrap
3. AnalysisOverviewCards
4. TopActionsCallout
5. **Strategy-map slot** — three states (see "Strategy-map slot renders three distinct states" requirement below for the state machine). When the map is `present`, this slot also renders the mid-page `DeepDiveCTA` immediately under the table.
6. EbitdaSection (only when `data.ebitdaTree` is present)
7. ValueChainDiagram (only when `data.valueChain.steps.length > 0`)
8. RiskBreakdown
9. ValueLeverSummary
10. OpportunitiesList
11. **QuickWinsMatrix** ← NEW (Diagnostic Tool Feedback #6) — renders when `opportunities.length >= 1`, omitted otherwise
12. DocumentUpload
13. **DeepDiveCTA (end-of-analysis variant)** — renders when `opportunities.length >= 1` (Diagnostic Tool Feedback #8)

Conditional sections that are omitted MUST NOT shift the relative order of the remaining sections.

This requirement supersedes the prior section ordering. Specifically:
- The standalone `Sc0redCTABanner` previously at position 4 was removed by the `redesign-strategy-map` Phase 5 change and is no longer rendered anywhere on the analysis page.
- The strategy-map slot's position (post-Phase-5) is between TopActionsCallout and EbitdaSection — moved up from its earlier "after OpportunitiesList" placement.
- The end-of-analysis `DeepDiveCTA` at position 13 was added by Stream A of the Diagnostic Tool Feedback (PR #350).
- The QuickWinsMatrix at position 11 is added by this change.

#### Scenario: Full-data analysis renders all 13 sections in order

- **WHEN** the analysis page loads with `strategyMap` populated, `ebitdaTree` populated, `valueChain.steps.length > 0`, and at least one opportunity
- **THEN** the rendered DOM contains, in order: header, strap, overview, top-actions, strategy-map, deep-dive-cta, ebitda, value-chain, risk-breakdown, value-lever, opportunities, quick-wins-matrix, document-upload, deep-dive-cta-end
- **AND** no element styled as a Sc0redCTABanner is rendered

#### Scenario: Analysis without opportunities omits the matrix and end-CTA

- **WHEN** the analysis page loads with `opportunities.length === 0`
- **THEN** the rendered DOM does not contain a `quick-wins-matrix` section
- **AND** does not contain a `deep-dive-cta-end` section
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
