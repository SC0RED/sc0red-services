## ADDED Requirements

### Requirement: Customer-triggered discovery escalation

When an automatic discovery result is incomplete, the customer SHALL be able to escalate discovery to a deeper tier from the confirmation screen. Escalation re-runs discovery for the existing scan at the chosen tier and merges any new candidates into the existing set (deduplicated by normalized URL), returning an updated verdict — without discarding the candidates already found. Expensive tiers SHALL run only on explicit customer request, never automatically.

#### Scenario: Search deeper merges new candidates

- **WHEN** the customer chooses "search deeper" on a scan in awaiting_confirmation
- **THEN** a broader web search runs, its new companies are merged into the candidate set (deduped), and the scan returns to awaiting_confirmation with an updated count and verdict

#### Scenario: Expensive tiers are not auto-run

- **WHEN** automatic discovery completes
- **THEN** deeper search and render-site are offered as choices but are not executed until the customer selects them

### Requirement: Headless render offered as a deferred opt-in rung

The "render the site" escalation SHALL be presented as an available action with clear cost framing, but its implementation is deferred. Until the render engine exists, selecting it SHALL inform the customer it is not yet available and suggest the deeper-search or upload alternatives, rather than failing silently.

#### Scenario: Render chosen before the engine exists

- **WHEN** the customer selects "render the site" and the render engine is not yet implemented
- **THEN** the customer is told it is not yet available and is pointed to search-deeper or upload-a-list
