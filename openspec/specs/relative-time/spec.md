# relative-time Specification

## Purpose

User-visible timestamps in the authenticated app render as relative time ("3 hours ago", "yesterday", "last week") with absolute time on hover. The component is hydration-safe: server emits absolute, client swaps to relative on mount, eliminating SSR/CSR drift.

## Requirements

### Requirement: Timestamps render as relative time with absolute tooltip

All user-visible timestamps in the authenticated app surface SHALL render as relative time (e.g., "3 hours ago", "yesterday", "last week"). Hovering the timestamp SHALL reveal the absolute time formatted in the user's locale and timezone.

#### Scenario: Recent timestamp renders relative

- **WHEN** an analysis has `analyzedAt: "2026-04-25T17:00:00Z"` and the current time is 3 hours later
- **THEN** the table cell renders "3 hours ago"; hovering reveals "April 25, 2026 at 5:00 PM PDT" (or equivalent for the user's locale)

#### Scenario: Older timestamp renders relative

- **WHEN** a timestamp is 5 days in the past
- **THEN** it renders "5 days ago" with the same hover-for-absolute affordance

#### Scenario: Very recent timestamp renders "just now"

- **WHEN** a timestamp is less than 30 seconds in the past
- **THEN** it renders "just now"

### Requirement: Relative time component is hydration-safe

The relative-time component SHALL render the absolute time on the server and swap to relative on client mount. This prevents hydration mismatch when "now" differs between server render time and client mount time.

#### Scenario: First paint shows absolute time

- **WHEN** the page renders for the first time (SSR)
- **THEN** the timestamp HTML contains the absolute time string (no "now"-relative computation)

#### Scenario: Client mount swaps to relative

- **WHEN** the page hydrates on the client
- **THEN** the timestamp swaps to its relative form ("3 hours ago"); no React hydration warning is emitted

### Requirement: Relative time used everywhere a timestamp displays

The `<RelativeTime>` component SHALL replace raw timestamp rendering in: the analyses table (`analyzedAt`), the dashboard recent items, the analysis detail page, the scan list, the portfolio scan card, and the team page (member join dates).

#### Scenario: Audit confirms no raw timestamps remain

- **WHEN** the codebase is searched for `toISOString` or raw ISO strings rendered to users in the authenticated surface
- **THEN** no instances remain (excluding tests, exports, and developer-only views); all are replaced by `<RelativeTime>`
