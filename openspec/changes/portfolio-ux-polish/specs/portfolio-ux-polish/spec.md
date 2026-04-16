## ADDED Requirements

### Requirement: Analysis detail page shows back-navigation to portfolio

When the analysis belongs to a portfolio scan (`scanId` is present), the analysis detail page SHALL display a "Back to Portfolio" link above the header.

#### Scenario: Portfolio company analysis shows back link

- **WHEN** a user views `/analysis/{id}` for a company with `scanId="scan-123"`
- **THEN** a "Back to Portfolio" link is visible, pointing to `/portfolio/scan-123`

#### Scenario: Standalone analysis does not show back link

- **WHEN** a user views `/analysis/{id}` for a standalone company scan (no `scanId`)
- **THEN** no "Back to Portfolio" link is shown

### Requirement: Portfolio grid cards maintain stable positions during updates

The portfolio heatmap grid SHALL render analyses in a deterministic order that does not change between poll cycles, even as companies transition from queued to analyzing to complete.

#### Scenario: Cards do not reorder when a new company completes

- **WHEN** the portfolio page polls and company X transitions from "Analyzing" to complete
- **THEN** all other cards remain in their current positions — company X's card updates in place
