## ADDED Requirements

### Requirement: Quantitative facts may be grounded with the provider's native web search

The pipeline SHALL ground quantitative real-world facts (disclosed financial figures, revenue-range estimates) using the AI provider's native web-search tool via the existing `signalfield_core` SDK (`query_structured` `tools` argument; `StructuredResponse.web_sources`). The system SHALL NOT introduce a separate third-party search/enrichment vendor.

#### Scenario: Web search returns cited sources

- **WHEN** a research question executes with web search enabled and the provider performs a search
- **THEN** the returned `web_sources` (url, title, snippet) are captured and attached to the resulting fact as citations

#### Scenario: No new search vendor

- **WHEN** the grounding step runs
- **THEN** it uses the provider-native `web_search` tool through the existing SDK — no Tavily/SerpAPI/Crunchbase (or similar) integration is added

### Requirement: Web search is enabled selectively, not on every call

Web search SHALL be enabled only on questions whose answer depends on the outside world (disclosed-figures lookup, revenue-range estimate) and SHALL NOT be enabled on questions the model answers from training knowledge (company type, revenue model, revenue mix, margin band, cost drivers, operating-model steps), to bound cost and latency.

#### Scenario: Qualitative question runs without search

- **WHEN** the revenue-model or revenue-mix question executes
- **THEN** web search is NOT enabled for that call

#### Scenario: Quantitative question runs with search

- **WHEN** the disclosed-figures or revenue-range question executes
- **THEN** web search IS enabled for that call

### Requirement: The shared AI call wrapper supports tools and returns web sources

`run_structured_ai_call` SHALL accept an optional `tools` argument (default none — existing callers unchanged) and SHALL return any `web_sources` produced by the call. It SHALL remain the single shared path for structured AI calls (no forked call path).

#### Scenario: Existing callers unchanged

- **WHEN** an existing caller invokes `run_structured_ai_call` without `tools`
- **THEN** behaviour is identical to before (no search, prior return shape preserved aside from an additive empty `web_sources`)

#### Scenario: Search-enabled caller receives sources

- **WHEN** a caller passes a web-search tool and the provider searches
- **THEN** the returned value includes the `web_sources` list

### Requirement: Search is best-effort and fails soft

A web-search failure or empty result SHALL NOT fail the analysis. The affected fact SHALL fall back to a non-disclosed provenance tier. Programming errors (not search misses) SHALL still propagate per fail-fast.

#### Scenario: Search finds nothing

- **WHEN** web search returns no usable figure for a private company
- **THEN** the revenue figure remains a derived estimate (not disclosed) and the analysis continues
