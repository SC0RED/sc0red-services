# Proposal — Activity Events Table Migration

> **STATUS: STUB — deferred until trigger fires.** This change exists so
> the carry-forward items from `webapp-ux-foundations-tier2` §5 don't
> drift out of sight. Do NOT implement until at least one trigger
> condition (see `design.md`) is met. When promoted, fill in
> `tasks.md` and run `/opsx:apply`.

## Why

The activity feed shipped in `webapp-ux-foundations-tier2` §5 (PR #197)
projects events from existing DynamoDB records at read time. Per
design D6, this was the right v1 trade-off — small data volumes, no
write-path overhead, simple code. But projection-at-read has known
gaps that v1 explicitly accepts:

- **Deletes can't be projected** — DynamoDB has no tombstones. So
  `scan_deleted` and `analysis_deleted` events never surface.
- **Scan completion has no timestamp** — scan records flip
  `status: complete` without writing a `completed_at`. No reliable
  source-of-truth time to project from.
- **Failures aren't timestamped distinctly** — same gap.
- **Companies > 100 in DynamoDB GSI page order silently miss** —
  read-time projection takes the first 100 companies and discards
  the cursor; recent `analysis_completed` events on companies past
  the page boundary disappear from the feed. The handler logs
  `activity_feed.company_page_capped` when this happens; consistent
  warnings are a trigger.
- **No real cursor pagination** — projection order isn't stable
  across calls; cursor-based "load more" can't be implemented
  honestly until we have a persistent ordered store.

This proposal captures the migration that closes those gaps: a
dedicated `janus-events-{env}` DynamoDB table where every domain
action writes a discrete event record at the time the action
happens. `GET /api/activity` becomes a simple cursor-paginated
query against that table.

## What Changes

When this proposal is promoted from stub → active:

1. **New DynamoDB table `janus-events-{env}`** — single-table per
   environment, GSI'd on `org_id` for org-scoped queries. PITR
   enabled. CDK construct in `infrastructure/`.

2. **Event-write helpers** — every handler that creates / completes
   / fails / deletes a scan or analysis writes an event record
   alongside the operational write. Most likely a thin
   `events_repo.put(event)` wrapper called from
   `scan_handlers.py`, `analysis_handlers.py`, `sqs_handler.py`,
   `step_function_handlers.py`, and the invitation handlers.

3. **Replace projection in `activity_handlers.py`** — `GET /api/activity`
   becomes a cursor-paginated query against the new table. Drop the
   four projection helpers (`_project_scan_started`, etc) and the
   `find_recent_by_org` / `find_by_org` calls in this file.

4. **Drop the cap-hit warning log + `_MAX_EVENTS` constant** — once
   reads are O(1) the page boundary issue goes away.

5. **Backfill (decide at promotion time)** — three options:
   (a) **Events start NOW** — no historical events, the feed starts
   empty; new events accrue from deploy onward.
   (b) **Synthetic backfill** — one-time job that walks existing
   scans/companies/users/invitations and writes equivalent events.
   (c) **DynamoDB Streams from operational tables** — captures
   ongoing changes without adding write paths to handlers; one-time
   backfill still needed for historical data.

6. **Frontend / API shape preserved** — the `ActivityEvent` shape on
   the wire stays the same so no frontend changes are required.

7. **Telemetry promoted** — `activity_feed.company_page_capped`
   warning + the v1 limitations docstring all come out.

## Triggers

Any one of the following promotes this stub to active:

| Trigger | How we detect it |
|---|---|
| `activity_feed.company_page_capped` warnings firing for any org consistently (≥ 1/day for a week) | CloudWatch Logs Insights query on the warning |
| Activity feed handler p95 latency > 500ms | CloudWatch metric on the API Lambda |
| Customer asks "show me deleted scans" or "show me failed analyses" | Sales / support channel |
| Multi-channel notifications (email, push) need an event stream to subscribe to | Product roadmap |
| Org passes ~500 companies (read-time projection cost grows linearly) | Dashboard metric |

When any trigger fires:
1. Open this stub change.
2. Re-validate the design decisions in `design.md` against the
   current state of the codebase (a year of drift may have invalidated
   some assumptions).
3. Pick the backfill option (5a / 5b / 5c above).
4. Fill in `tasks.md`.
5. Run `/opsx:apply`.

## Capabilities

### Modified Capabilities

- **`activity-feed`** (the spec written by tier-2 §5; will move from
  read-time-projection to events-table-backed). The user-visible
  contract is unchanged — same event types, same DTO shape, same
  polling cadence. The implementation behind the endpoint changes.

### New Capabilities

None. This is an internal architecture migration, not a user-facing
feature change.

## Impact

**Backend**:
- New DynamoDB table + CDK construct
- New `events_repository.py`
- Event-write call sites added to ~6 existing handlers
- `activity_handlers.py` cut over from projection to query
- New `events.py` model (Pydantic) for the persisted event shape
- Decommission paths: drop the four `_project_*` helpers + the
  cap-hit warning + `_MAX_EVENTS`

**Infrastructure**:
- One new DynamoDB table per environment (development, testing,
  production)
- IAM grants for the API Lambda + writer Lambdas
- PITR config matching the existing `janus-{env}` table

**Frontend**:
- None expected — the wire DTO shape is preserved

**Tests**:
- New `test_events_repository.py`
- Integration tests for the write-on-action wiring
- Backend pytest cap update if events table covers more event types
  (e.g., we add `scan_completed` and `analysis_failed` to the union)
- Frontend type-parity check (`check_activity_event_type_parity.py`)
  needs updating if new event types land

## What We're NOT Doing

- **Not implementing now.** This is a stub. Read the status note at
  the top.
- **Not redesigning the activity-feed wire shape.** `ActivityEvent`
  stays as-is.
- **Not adding real-time push.** Polling at 30s remains; SSE/websockets
  is a separate proposal.
- **Not backfilling automatically without a decision.** The backfill
  strategy (5a/5b/5c) gets chosen at promotion time, not now.

## Open Questions (resolve at promotion time)

1. **Sync write vs CDC** — option 1 (handlers write events directly)
   vs option 2 (DynamoDB Streams → Lambda → events table). Trade-off
   covered in `design.md`.
2. **Backfill scope** — accept "events start NOW" or backfill from
   existing records?
3. **Event retention** — DynamoDB TTL on events older than 90 days?
   Keep forever? Spec says 90d for analytics in `analytics-events`
   log group; events table could match.
4. **Should `scan_completed` / `*_failed` write happen in the
   handler that flips the status, or in the SQS worker that detects
   completion?** Likely the handler — closer to the source of truth.
