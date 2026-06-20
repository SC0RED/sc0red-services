## ADDED Requirements

### Requirement: Discovery returns a structured verdict

Portfolio discovery SHALL return a structured verdict alongside the candidate list, containing: the method that produced the result, the candidate count, a completeness signal (one of: full site list, site blocked, web-search subset, genuinely empty), and the set of next actions available to the customer (a subset of: search deeper, render site, upload list). The verdict SHALL be derived from existing discovery signals (which path produced candidates and whether the site fetch failed). A client-side-rendered firm (empty site scrape recovered by web search) maps to `web_search_subset` — it is not a separate completeness value, since the message and next actions are identical.

#### Scenario: Client-side-rendered firm

- **WHEN** the site scrape finds no companies because the listing page is a client-side-rendered shell and the web-search fallback returns a small subset
- **THEN** the verdict reports method=web-search, the subset count, completeness=web_search_subset, and next actions including search-deeper and upload-list

#### Scenario: Full site list

- **WHEN** the site scrape yields the firm's full company list
- **THEN** the verdict reports method=site, the count, completeness=full-site-list, and does not push escalation as necessary

### Requirement: Verdict rendered as a meaningful customer message

The portfolio scan UI SHALL render the verdict as a plain-language message explaining what was found and why it may be incomplete, rather than only a bare count, and SHALL present the verdict's available next actions as explicit choices.

#### Scenario: Incomplete result explains itself and offers choices

- **WHEN** a verdict indicates a web-search-subset or blocked site with a partial count
- **THEN** the customer sees a message stating the cause and the partial count, plus actionable choices (e.g. search deeper / upload a list) alongside proceeding with the current results
