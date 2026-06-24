## ADDED Requirements

### Requirement: Web-search fallback recovers a portfolio when site discovery is thin

When site-derived discovery (heuristic + AI extraction over the firm's own pages, merged) yields fewer companies than a configured low-water mark, the discovery step SHALL run a web-search-grounded AI call (via `run_grounded_ai_call`, the provider's native `web_search` tool) to recover the firm's notable current portfolio companies as `{name, url}` candidates. The fallback prompt and output schema SHALL be externalized under `src/pipeline/prompts/`.

#### Scenario: Opaque/embedded-data site below threshold triggers the fallback

- **WHEN** site discovery returns a company count below the threshold
- **THEN** the step runs the web-search-grounded fallback and obtains additional candidate companies

#### Scenario: Healthy site discovery skips the fallback

- **WHEN** site discovery returns a company count at or above the threshold
- **THEN** the web-search fallback does NOT run (no search cost/latency is incurred)

### Requirement: The fallback trigger is a configurable low-water mark

The threshold that triggers the fallback SHALL be configurable, defaulting to `0` (i.e. fire only when site discovery found nothing) and raisable without code changes to also catch thin/partial scrapes.

#### Scenario: Default threshold rescues zero-result scrapes

- **WHEN** the threshold is the default and site discovery returns 0 companies
- **THEN** the fallback runs

### Requirement: Site results remain authoritative; fallback is strictly additive

The web-search fallback SHALL NOT replace or override site-derived results. Its candidates SHALL be unioned with the site results (deduplicated by normalized URL domain) and only ADD companies the site did not surface. The firm's own site remains the source of truth for its current portfolio.

#### Scenario: Fallback does not displace site companies

- **WHEN** the fallback runs and returns companies already found from the site
- **THEN** duplicates are removed by domain and the site-derived entries are retained

### Requirement: The fallback fails soft

A failure or empty result from the web-search fallback (rate limit, schema error, search miss) SHALL yield no additional candidates and SHALL NOT raise or fail the portfolio scan. Programming errors (not search misses) still propagate per fail-fast.

#### Scenario: Search failure does not crash the scan

- **WHEN** the web-search fallback errors or returns nothing
- **THEN** discovery continues with the site-derived results (possibly zero) and the existing "could not identify portfolio companies" diagnostic
