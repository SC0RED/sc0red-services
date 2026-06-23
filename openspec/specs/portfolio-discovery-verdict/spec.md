# portfolio-discovery-verdict Specification

## Purpose
TBD - created by archiving change customer-guided-portfolio-discovery. Update Purpose after archive.
## Requirements
### Requirement: Discovery returns a structured verdict

Portfolio discovery SHALL return a structured verdict alongside the candidate list, containing: the method that produced the result, the candidate count, a completeness signal (one of: full site list, partial site list, site blocked, web-search subset, web-search exhausted, genuinely empty), and the set of next actions available to the customer (a subset of: search deeper, render site, upload list). The verdict SHALL be derived from existing discovery signals (which path produced candidates and whether the site fetch failed). A client-side-rendered firm (empty site scrape recovered by web search) maps to `web_search_subset` — it is not a separate completeness value, since the message and next actions are identical.

#### Scenario: Client-side-rendered firm

- **WHEN** the site scrape finds no companies because the listing page is a client-side-rendered shell and the web-search fallback returns a small subset
- **THEN** the verdict reports method=web-search, the subset count, completeness=web_search_subset, and next actions including search-deeper and upload-list

#### Scenario: Full site list

- **WHEN** the site scrape yields the firm's full company list AND there is positive reason to believe it is complete
- **THEN** the verdict reports method=site, the count, completeness=full-site-list

### Requirement: A non-zero site scrape SHALL NOT be inferred to be complete

A non-zero site scrape does not imply the firm's full portfolio was found — client-side-rendered shells, paginated JSON islands, and logo grids commonly surface only a partial subset. The verdict SHALL NOT classify a result as `full_site_list` (and SHALL NOT hide escalation) solely because the site returned one or more companies. Absent a positive completeness signal, a non-zero site result SHALL be classified `partial_site_list`, whose message conveys that the list may be incomplete and which offers `search_deeper` and `upload_list`. `full_site_list` (the only completeness that omits `search_deeper`) is reserved for results believed complete.

The verdict's `available_actions` SHALL always include `upload_list`, and SHALL include `search_deeper` for every completeness except `full_site_list`.

#### Scenario: Partial scrape still offers escalation

- **WHEN** the site scrape yields a small non-zero number of companies (e.g. 4 of a much larger portfolio) with no positive signal that the list is complete
- **THEN** the verdict reports completeness=partial_site_list with a message that the list may be incomplete, and `available_actions` includes search-deeper and upload-list (escalation is NOT hidden)

#### Scenario: Escalation is never hidden on an uncertain result

- **WHEN** any completeness other than `full_site_list` is reported
- **THEN** `available_actions` includes both `search_deeper` and `upload_list`

### Requirement: Verdict rendered as a meaningful customer message

The portfolio scan UI SHALL render the verdict as a plain-language message explaining what was found and why it may be incomplete, rather than only a bare count, and SHALL present the verdict's available next actions as explicit choices.

#### Scenario: Incomplete result explains itself and offers choices

- **WHEN** a verdict indicates a web-search-subset or blocked site with a partial count
- **THEN** the customer sees a message stating the cause and the partial count, plus actionable choices (e.g. search deeper / upload a list) alongside proceeding with the current results

