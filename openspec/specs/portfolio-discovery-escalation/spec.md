# portfolio-discovery-escalation Specification

## Purpose
TBD - created by archiving change customer-guided-portfolio-discovery. Update Purpose after archive.
## Requirements
### Requirement: Customer-triggered discovery escalation

When an automatic discovery result is incomplete, the customer SHALL be able to escalate discovery to a deeper tier from the confirmation screen. Escalation re-runs discovery for the existing scan at the chosen tier and merges any new candidates into the existing set (deduplicated by normalized URL), returning an updated verdict — without discarding the candidates already found. Expensive tiers SHALL run only on explicit customer request, never automatically.

#### Scenario: Search deeper merges new candidates

- **WHEN** the customer chooses "search deeper" on a scan in awaiting_confirmation
- **THEN** a broader web search runs, its new companies are merged into the candidate set (deduped), and the scan returns to awaiting_confirmation with an updated count and verdict

#### Scenario: Expensive tiers are not auto-run

- **WHEN** automatic discovery completes
- **THEN** deeper search and render-site are offered as choices but are not executed until the customer selects them

### Requirement: Deeper search converges and reports exhaustion

A deeper search SHALL report how many NEW companies it added to the existing set. Deeper search SHALL converge: when a round of deeper search adds no new companies, the system SHALL treat web search as exhausted for that firm. On exhaustion the verdict SHALL communicate that the deeper search found no additional companies and SHALL direct the customer to upload a list for a guaranteed-complete result, and SHALL stop presenting further deeper-search as productive (e.g. completeness `web_search_exhausted`). The customer SHALL NOT be left clicking "search deeper" indefinitely with no signal of diminishing returns.

Messaging SHALL be honest that web search is recall, not enumeration: even an exhausted deeper search is not guaranteed to be the complete portfolio, and upload remains the only path to a complete list.

#### Scenario: Deeper search adds new companies

- **WHEN** the customer searches deeper and the search finds companies not already on the scan
- **THEN** the new companies are merged (deduped), the verdict reports the updated count and how many were newly added, and search-deeper remains available

#### Scenario: Deeper search is exhausted

- **WHEN** a round of deeper search adds zero new companies
- **THEN** the verdict reports completeness=web_search_exhausted with a message that no more were found via search and that the customer should upload a list for completeness, and deeper-search is no longer presented as productive

### Requirement: Headless render offered as a deferred opt-in rung

The "render the site" escalation SHALL be presented as an available action with clear cost framing, but its implementation is deferred. Until the render engine exists, selecting it SHALL inform the customer it is not yet available and suggest the deeper-search or upload alternatives, rather than failing silently.

#### Scenario: Render chosen before the engine exists

- **WHEN** the customer selects "render the site" and the render engine is not yet implemented
- **THEN** the customer is told it is not yet available and is pointed to search-deeper or upload-a-list

