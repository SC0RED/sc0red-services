## ADDED Requirements

### Requirement: Sidebar surfaces a top-level Connect entry

The authenticated sidebar SHALL include a top-level navigation entry for connecting an AI assistant, labelled "Connect AI" (a plain-language label — MCP terminology stays on the page, not the nav), available to all authenticated users (not admin-gated). The entry SHALL link to `/connect`, where the self-serve MCP Connect page now lives. The Connect page SHALL NOT also appear as a section inside Settings — the top-level entry is its single home.

Until the user has visited `/connect` at least once, the entry MAY show a small, muted "New" indicator to raise awareness; the indicator SHALL clear after the first visit and SHALL NOT reappear on the same device.

#### Scenario: Connect is reachable from the main nav

- **WHEN** any authenticated user views the sidebar
- **THEN** a "Connect AI" entry is present and navigates to `/connect`

#### Scenario: Connect is not duplicated in Settings

- **WHEN** the user opens Settings
- **THEN** there is no separate "Connect" section there (the top-level nav entry is the only doorway)

### Requirement: Old Connect routes redirect to `/connect`

Moving the Connect page to `/connect` SHALL NOT break existing links. Requests to the former routes `/settings/connect` and `/settings/connected-apps` SHALL redirect to `/connect`.

#### Scenario: A bookmark to the old Connect route still works

- **WHEN** a user navigates to `/settings/connect` (or `/settings/connected-apps`)
- **THEN** they are redirected to `/connect` and see the Connect page
