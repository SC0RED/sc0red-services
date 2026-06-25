# portfolio-discovery-provenance Specification

## Purpose
Defines per-candidate source/confidence provenance for discovered portfolio companies (site / web_search / upload / provided_url) and how the verdict surfaces the firm page that site-derived companies were read from as a group-level trust anchor.
## Requirements
### Requirement: Each discovered company carries its source

Every discovered candidate SHALL carry a `source` indicating where it came from: `site` (read from the firm's own website), `web_search` (recalled via grounded web search), `upload` (from a customer-supplied file), or `provided_url` (fetched from a customer-supplied URL). Confidence is derived from source: `web_search` is low-confidence; all others are high-confidence. The verdict SHALL surface the exact firm page that site-derived companies were read from (e.g. `insightpartners.com/portfolio`) as a group-level trust anchor.

#### Scenario: Mixed result is attributable per company

- **WHEN** discovery returns some companies from the firm's site and some from web search
- **THEN** each candidate carries its `source`, and the verdict reports the site page read plus the count from each source — the customer can tell which companies are reliable

### Requirement: The UI marks reliable companies distinctly from best-effort

The confirmation screen SHALL visually distinguish high-confidence (site / upload / provided_url) companies from low-confidence (web_search) companies, showing the exact site source for the reliable group. Low-confidence web-search rows SHALL NOT be pre-selected and SHALL be presented under a "review before including" affordance with their URLs flagged as unverified; high-confidence rows MAY be pre-selected.

#### Scenario: Reliable pre-selected, web-search opt-in

- **WHEN** the confirmation screen shows a mixed result
- **THEN** site/upload/provided_url companies are grouped as reliable (with the source page shown) and pre-selected, while web-search companies appear unchecked under a "found via search — verify" heading

### Requirement: A trusted source wins over web search in deduplication

When merging web-search candidates into a set that already contains higher-confidence (site / upload / provided_url) companies, a web-search candidate SHALL be dropped if its normalized name OR its normalized URL key already exists in the trusted set. Normalization of names SHALL be conservative (lowercase, strip common company suffixes, collapse punctuation/whitespace). A trusted (non-web-search) company SHALL never be dropped in favor of a web-search duplicate. This applies both to the initial web-search fallback and to "search deeper".

#### Scenario: Site company is not repeated by web search

- **WHEN** the firm's site yields `Acme (acme.com)` and a web search returns `Acme (acme.in)`
- **THEN** the web-search `Acme` is dropped (the site's `Acme` is kept) — the same company does not appear twice

#### Scenario: TLD duplicates within web search collapse

- **WHEN** a web search returns the same company under two TLDs (`xyz.com` and `xyz.in`)
- **THEN** only one is kept (deduped by normalized name)

### Requirement: Incompleteness is explained honestly and reliable-first

When the result may be incomplete, the customer-facing message SHALL lead with what was read reliably (count + the firm page) and then explain the limitation in plain, accurate terms. The explanation SHALL NOT attribute the limit to a browser "cross-origin" restriction (discovery runs server-side); when the cause is client-side rendering it SHALL be described as the site building its list in the browser after the page loads.

#### Scenario: Dynamic site explained without false technical claims

- **WHEN** the firm's site renders its portfolio client-side and the site scrape was thin
- **THEN** the message states how many were read from the firm's site and explains the list loads dynamically in the browser, rather than claiming a cross-origin block

