# authenticated-layout Specification

## Purpose
TBD - created by archiving change sidebar-layout-fix. Update Purpose after archive.
## Requirements
### Requirement: Sidebar persists across authenticated page navigations
The sidebar component SHALL be rendered in a shared layout so it remains mounted during client-side navigation between authenticated pages. It SHALL NOT remount when navigating between dashboard, analyses, scan, team, analysis detail, or portfolio pages.

#### Scenario: Navigate between dashboard and scan
- **WHEN** user clicks "New Scan" in the sidebar while on the dashboard
- **THEN** the sidebar stays mounted (no remount, no flicker), only the page content changes

#### Scenario: Navigate between any two authenticated pages
- **WHEN** user navigates between any combination of dashboard, analyses, scan/new, team, analysis/[id], portfolio/[scanId]
- **THEN** the sidebar component instance persists (verified by stable useSession state, no Team icon flicker)

### Requirement: No duplicate SessionProvider wrappers
There SHALL be exactly one SessionProvider in the component tree for authenticated pages, provided by the root layout's SessionWrapper. Individual pages SHALL NOT render their own SessionProvider or SessionWrapper.

#### Scenario: Dashboard page renders without extra SessionProvider
- **WHEN** the dashboard page loads
- **THEN** it uses the root layout's SessionProvider (no nested SessionProvider in its tree)

### Requirement: Pages render content only
Authenticated page components SHALL render only their page-specific content. They SHALL NOT render DashboardSidebar, the main element wrapper, or Breadcrumbs — these are provided by the shared layout.

#### Scenario: Page file contains no sidebar import
- **WHEN** any authenticated page file is inspected
- **THEN** it does not import or render DashboardSidebar

### Requirement: Route URLs unchanged

The `(authenticated)` route group SHALL NOT affect URL paths. All existing routes (`/dashboard`, `/analyses`, `/scan/new`, `/team`, `/analysis/[id]`, `/portfolio/[scanId]`, `/settings`) SHALL continue to work at the same URLs.

#### Scenario: Dashboard URL unchanged

- **WHEN** user navigates to `/dashboard`
- **THEN** the dashboard page loads (route group parentheses are not part of the URL)

#### Scenario: Settings route resolves under (authenticated)

- **WHEN** user navigates to `/settings`
- **THEN** the settings page loads under the `(authenticated)` route group, with the sidebar visible

### Requirement: Sidebar includes a Settings entry

The sidebar SHALL include a "Settings" entry that navigates to `/settings`. The entry SHALL appear in the same nav set as Dashboard, New Scan, Analyses, and Team. Existing sidebar persistence requirements continue to apply (the entry does not remount on navigation).

#### Scenario: Settings entry visible to all authenticated users

- **WHEN** any authenticated user views the sidebar
- **THEN** a "Settings" link is rendered (not gated by role) navigating to `/settings`

#### Scenario: Settings nav participates in sidebar persistence

- **WHEN** the user navigates from `/dashboard` to `/settings` via the sidebar
- **THEN** the sidebar instance persists (no remount, no flicker), per the existing persistence requirement

