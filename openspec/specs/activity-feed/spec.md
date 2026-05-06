# activity-feed Specification

## Purpose

Org-scoped recent-activity panel projected at request time from existing DynamoDB records. The feed surfaces scan, analysis, and team-member events in a sidebar panel with an unread badge, polling at a fixed cadence while the user is on the app.

## Requirements

### Requirement: Backend exposes a recent-activity endpoint

The backend SHALL expose `GET /api/activity?limit=N&cursor=...` returning recent org-level events. Events SHALL be projected at request time from existing DynamoDB records (scan creates/completes/deletes, analysis completes/deletes, member invites/joins). Response SHALL be a chronologically-sorted (newest first) array of event DTOs with cursor-based pagination.

#### Scenario: User fetches recent activity

- **WHEN** the user's frontend calls `GET /api/activity?limit=20`
- **THEN** the response is `{events: [...], cursor: "..."}` with up to 20 events; each event has `type`, `actor`, `target`, `timestamp`, and a human-readable `summary`

#### Scenario: Pagination cursor advances

- **WHEN** the response includes a cursor and the frontend calls `GET /api/activity?limit=20&cursor=...`
- **THEN** the next 20 events are returned; the response cursor advances or is absent if no more events

#### Scenario: Org isolation

- **WHEN** a user from org A calls `/api/activity`
- **THEN** the response contains only events from org A; no cross-org leakage

### Requirement: Frontend renders the activity feed in a sidebar panel

The frontend SHALL render an activity panel in the sidebar (or accessible from the sidebar). The panel SHALL display recent events chronologically, polling `/api/activity` every 30 seconds while open. A bell icon SHALL show an unread badge when new events arrive since the user last viewed the panel.

#### Scenario: Panel renders recent events

- **WHEN** the user opens the activity panel
- **THEN** the most recent 20 events are displayed; each shows the actor (name), action ("created scan", "deleted analysis"), target (scan/analysis name), and relative timestamp

#### Scenario: Unread badge appears on new events

- **WHEN** the user closes the panel, a new event is fired by another user, and the next poll fires
- **THEN** the bell icon shows an unread count badge

#### Scenario: Opening the panel marks events read

- **WHEN** the user clicks the bell icon to open the panel
- **THEN** the unread badge clears; the user's last-viewed timestamp updates locally

### Requirement: Event types covered in v1

The activity feed v1 SHALL surface at minimum these event types:

| Event type | Trigger |
|---|---|
| `scan.created` | A user starts a scan (`POST /api/scan/start`) |
| `scan.completed` | A scan transitions to status `complete` |
| `scan.failed` | A scan transitions to status `failed` |
| `scan.deleted` | A scan is deleted |
| `analysis.completed` | An analysis is set with `analyzed_at` |
| `analysis.failed` | An analysis is set with `error` |
| `analysis.deleted` | An analysis is deleted |
| `member.invited` | A user invites another via the team page |
| `member.joined` | An invited user accepts the invite |

#### Scenario: Scan creation surfaces in the feed

- **WHEN** Bob starts a portfolio scan
- **THEN** within 30 seconds Alice's activity panel poll returns a `scan.created` event with Bob as actor and the scan as target

#### Scenario: Member events surface

- **WHEN** Alice invites carol@example.com and Carol later accepts
- **THEN** the activity feed shows a `member.invited` event when invited and a `member.joined` event when Carol accepts
