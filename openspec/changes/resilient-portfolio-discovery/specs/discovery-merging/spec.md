## ADDED Requirements

### Requirement: Web-search fallback candidates are validation-tier

Candidates produced by the web-search fallback (see `portfolio-discovery-web-fallback`) SHALL be merged into the `needs_validation` tier — never `auto_included`. They are deduplicated by normalized URL domain against the site-derived results, so every model-sourced candidate is AI-validated by the validation step before it is scanned. `auto_included` remains reserved for the high-confidence heuristic∩AI intersection drawn from the firm's own site.

#### Scenario: Fallback candidate requires validation

- **WHEN** the web-search fallback returns `{name: "Sophos", url: "https://sophos.com"}` and the site did not surface it
- **THEN** Sophos is placed in `needs_validation` (not `auto_included`) and is AI-validated before scanning

#### Scenario: Fallback candidate duplicating a site company is deduped

- **WHEN** a fallback candidate shares a normalized domain with a site-derived company
- **THEN** it is not added again; the site-derived entry (and its tier) is retained

## MODIFIED Requirements

### Requirement: Meaningful feedback for 0 results

When site-derived discovery yields a company count below the fallback threshold, the discovery step SHALL FIRST attempt the web-search fallback (`portfolio-discovery-web-fallback`) before concluding the result is empty. Only when both site discovery AND the fallback yield 0 companies SHALL the response include a diagnostic message explaining why: "No portfolio pages found at expected paths" or "Page found but no portfolio company links detected" or "This appears to be a professional services firm, not a PE firm with portfolio companies."

#### Scenario: Fallback rescues a zero-result scrape

- **WHEN** site discovery returns 0 companies but the web-search fallback recovers candidates
- **THEN** those candidates are returned (in `needs_validation`) and no "0 results" diagnostic is emitted

#### Scenario: Non-PE firm (both paths empty)

- **WHEN** discovery runs on bdo.com (accounting firm) and neither site discovery nor the fallback finds portfolio companies
- **THEN** the response includes `{companies: [], message: "This appears to be a professional services firm. Portfolio discovery works best with PE/VC firm websites."}`

#### Scenario: PE firm with unusual structure (both paths empty)

- **WHEN** discovery runs, all links are filtered, and the fallback also yields nothing
- **THEN** the response includes `{companies: [], message: "Found links but couldn't identify portfolio companies. The site may use an unusual page structure."}`
