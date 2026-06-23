## MODIFIED Requirements

### Requirement: Worker processes portfolio discovery messages

The SQS worker SHALL recognise messages with `type="portfolio_discovery"` and invoke `FactoryManager.run_portfolio_discovery(...)` to execute the `DiscoverPortfolio` → `ValidatePortfolioCompanies` pipeline. On success, it SHALL update the scan record with `status="awaiting_confirmation"`, `portfolio_companies=[...]`, `progress=20`, and the structured discovery verdict (method, count, completeness signal, available next actions). The discovery message SHALL also carry an optional escalation tier so the customer can re-run discovery at a deeper tier for an existing scan; an escalation re-runs discovery and merges new candidates into the existing set (deduplicated) before returning to `awaiting_confirmation`.

#### Scenario: Worker runs discovery and persists results with a verdict

- **WHEN** the worker receives a message `{type: "portfolio_discovery", url, org_id, user_id, scan_id}`
- **THEN** it runs the portfolio discovery pipeline and updates the scan record with `status="awaiting_confirmation"`, the discovered company list, and the discovery verdict

#### Scenario: Worker ignores unknown message types

- **WHEN** the worker receives a message with `type="unknown_type"`
- **THEN** it raises and triggers SQS retry via `batchItemFailures`, so the bug is surfaced in CloudWatch rather than silently dropped

#### Scenario: Escalation re-runs discovery for an existing scan

- **WHEN** the worker receives a portfolio discovery message carrying an escalation tier for an existing scan in `awaiting_confirmation`
- **THEN** it runs discovery at that tier, merges any new candidates into the existing list (deduplicated), and returns the scan to `awaiting_confirmation` with an updated count and verdict
