## ADDED Requirements

### Requirement: Sidebar includes a Settings entry

The sidebar SHALL include a "Settings" entry that navigates to `/settings`. The entry SHALL appear in the same nav set as Dashboard, New Scan, Analyses, and Team. Existing sidebar persistence requirements continue to apply (the entry does not remount on navigation).

#### Scenario: Settings entry visible to all authenticated users

- **WHEN** any authenticated user views the sidebar
- **THEN** a "Settings" link is rendered (not gated by role) navigating to `/settings`

#### Scenario: Settings nav participates in sidebar persistence

- **WHEN** the user navigates from `/dashboard` to `/settings` via the sidebar
- **THEN** the sidebar instance persists (no remount, no flicker), per the existing persistence requirement

## MODIFIED Requirements

### Requirement: Route URLs unchanged

The `(authenticated)` route group SHALL NOT affect URL paths. All existing routes (`/dashboard`, `/analyses`, `/scan/new`, `/team`, `/analysis/[id]`, `/portfolio/[scanId]`, `/settings`) SHALL continue to work at the same URLs.

#### Scenario: Dashboard URL unchanged

- **WHEN** user navigates to `/dashboard`
- **THEN** the dashboard page loads (route group parentheses are not part of the URL)

#### Scenario: Settings route resolves under (authenticated)

- **WHEN** user navigates to `/settings`
- **THEN** the settings page loads under the `(authenticated)` route group, with the sidebar visible
