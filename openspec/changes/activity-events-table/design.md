# Design — Activity Events Table Migration

> **STUB.** Read `proposal.md` first. The design decisions below are
> v1 sketches; re-validate at promotion time against current codebase
> state.

## Context

`webapp-ux-foundations-tier2` §5 shipped the activity feed in PR #197
with read-time projection from existing operational records (scans,
companies, users, invitations). Per `webapp-ux-foundations-tier2`
`design.md` D6, the v1 trade-off was deliberate:

> **Why no events table:** Premature. Adds a write path everywhere.
> Projection at read time is "good enough" for v1 with the right
> caching and the small data set today. When projection becomes too
> slow (>500ms), we add an events table and a write-side projection.

This proposal captures the migration path when "good enough" stops
being good enough. See `proposal.md` for the trigger conditions.

## v1 (today) vs v2 (this proposal)

```
                         v1 (read-time projection)
                         ──────────────────────────
                         GET /api/activity
                              │
                              ▼
   ┌──────────────────────────────────────────────────┐
   │  activity_handlers.handle_get_activity           │
   │    scan_repo.find_recent_by_org()    ──────►     │
   │    company_repo.find_by_org(limit=100) ──────►   │  (4 reads)
   │    user_repo.find_by_org()           ──────►     │
   │    invitation_repo.find_by_org()     ──────►     │
   │                                                  │
   │    project each → sort → cap at 100 → return     │
   └──────────────────────────────────────────────────┘
   GAPS:
   - no scan_deleted / analysis_deleted events
   - no scan_completed / *_failed events
   - companies > 100 silently dropped
   - cursor pagination is fake
```

```
                         v2 (events table)
                         ─────────────────
   Each domain action writes an event at the time it happens:

   scan_handlers.handle_scan_start   →  events_repo.put({type:"scan_started",  org_id, ts, ...})
   sqs_handler ... status=complete    →  events_repo.put({type:"scan_completed", org_id, ts, ...})
   sqs_handler ... status=failed      →  events_repo.put({type:"scan_failed",    org_id, ts, ...})
   analysis_handlers ... analyzed_at  →  events_repo.put({type:"analysis_completed", ...})
   scan_handlers.handle_delete_scan   →  events_repo.put({type:"scan_deleted",   ...})
   ... etc

                              ▼
   ┌──────────────────────────────────────────────────┐
   │  GET /api/activity                               │
   │    events_repo.find_by_org(                      │
   │      org_id, limit=N, cursor=...                 │
   │    )                                             │
   │    → query GSI sorted by sk DESC                 │
   │    → return events + cursor                      │
   └──────────────────────────────────────────────────┘
```

## Decisions (v1 sketches — re-validate at promotion time)

### D1. Single dedicated table `janus-events-{env}`, not a section of `janus-{env}`

**Decision:** stand up a NEW table rather than adding event records to
the existing operational table.

**Why:**
- Separate scaling profile — events are write-heavy (every domain
  action) and tail-read (mostly recent items only). Keeping them out
  of the operational table avoids contention.
- Independent retention — events probably get TTL'd after 90 days
  (matching the analytics log retention); operational records are
  kept forever.
- Clean teardown if we ever sunset the activity feed without
  affecting operational data.
- Independent IAM — only handlers and the activity API need write/read
  on events.

**Why not in operational table:** would require a 5th GSI. The
existing 4 GSIs are all in use; adding GSI5 just for events is the
same operational complexity as a new table without the isolation
benefits.

### D2. Sync write from handlers, NOT CDC

**Decision:** every handler that creates/completes/fails/deletes a
scan or analysis calls `events_repo.put(event)` synchronously after
the operational write.

**Why:**
- Simplest path. No new infra (DynamoDB Streams + Lambda + IAM).
- Failure mode is clearer — if the operational write succeeds and
  the events write fails, log it; the operational state of truth is
  the operational table, not the events table. Eventual consistency
  via a backfill cron OR accept the rare gap.
- CDC adds latency we don't need (events appear in the feed seconds
  after the action) — sync write is real-time.

**Trade-off:** every handler now has a dependency on the events repo.
Mitigated by making `events_repo.put` non-blocking on failure (log
+ continue). Re-evaluate at promotion time if the codebase has grown
in a way that makes CDC more attractive.

**Alternative considered (CDC):** DynamoDB Streams on the operational
table → Lambda → projects to events table. No handler changes. But:
- 1-2s lag from action → event visible
- New Lambda + IAM + Stream config
- Failure modes are subtler (DLQ for the projector)
- Schema-coupling between projector and operational records becomes
  a hidden contract

### D3. Event ID is deterministic, not UUID

**Decision:** event ID = `{type}:{source-record-id}:{timestamp}` —
same shape as v1. Carries forward to the persisted record so reads
match the existing wire shape.

**Why:** dedup across retries (handler runs twice → second event
write is idempotent via PK collision).

### D4. Single-table key shape

```
PK: ORG#{org_id}
SK: EVT#{ISO8601-timestamp}#{event_id}
GSI1PK: ORG#{org_id}
GSI1SK: EVT#{ISO8601-timestamp}#{event_id}
```

Mirrors the existing convention. Sort key prefix with `EVT#` allows
range queries by date if we ever need them (e.g., "events in the
last hour").

### D5. Retention via DynamoDB TTL

**Decision:** every event record carries a `ttl` attribute set to
90 days from creation. DynamoDB TTL deletes them automatically.

**Why:** matches the 90d retention on the `/janus/{env}/analytics-events`
CloudWatch Logs group. Long enough for "what happened this quarter",
short enough to keep table size bounded.

**Trade-off:** "show me all events ever" queries don't work past 90d.
At promotion time, decide if any consumer needs longer retention.

### D6. Backfill — pick at promotion time

Three options, in increasing scope:

**Option A — events start NOW.** No historical events. The feed is
empty on deploy day; new events accrue from there.
- Pros: zero backfill work, deploy is reversible
- Cons: existing scans/analyses don't appear; users with a "what
  happened this week" expectation see nothing for 7 days

**Option B — synthetic backfill from existing records.** One-time
script that walks `scan` / `company` / `user` / `invitation` records
and writes equivalent events into the new table.
- Pros: feed is populated on deploy day; users see continuity
- Cons: backfill events have approximate timestamps for the
  carry-forward gaps (no real `scan_completed` time, etc) — same
  limitations as v1 projection but baked in permanently
- ~200 LoC for the script, ~1 hour to run on production

**Option C — DynamoDB Streams from operational tables for catch-up.**
Enable Streams on the existing operational table, point a projector
Lambda at it, project to events. Combined with handler sync writes
this gives both real-time AND historical catch-up.
- Pros: no synthetic timestamps; events match real action times
- Cons: Streams must have been on for the period you want to
  backfill — if not, falls back to option B for older events
- Most complex option; only worth it if real-time CDC is needed
  for OTHER reasons too

**Recommendation at promotion time:** start with option A. Promote
to option B if customer feedback shows users miss the historical
context.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Handler-side write path failure leaves events out of sync with operational state | Log warnings; rely on the operational table as source of truth; backfill cron if drift is detected |
| Events table grows unbounded | TTL at 90d + monitor table size in CloudWatch |
| Schema drift between operational records and event records | Pydantic models on both sides + integration test that creates a scan and asserts an event lands |
| Existing v1 query path is still hit during deploy window | Feature-flag the cutover via env var or release in two stages (write events, then switch reads) |
| Frontend assumes wire DTO shape — must not break | E2E test that exercises the full flow before deploy |

## Migration Plan (when promoted)

Two-stage rollout to keep the door open for rollback:

**Stage 1 — write only.**
1. Land the new table + IAM (no consumers yet)
2. Add `events_repo.put` calls to handlers
3. Verify events accruing (CloudWatch Insights query against the
   table)
4. Old read path still serves `/api/activity`

**Stage 2 — switch reads.**
1. Implement the new query path in `activity_handlers.py`
2. Feature-flag: `ACTIVITY_FEED_USE_EVENTS_TABLE=true`
3. Roll out to development first, observe for a week
4. Promote to testing, then production
5. Remove the v1 projection helpers + `_MAX_EVENTS` + cap-hit log
6. Remove the feature flag

Rollback: flip the feature flag, redeploy, the old projection
returns. Events written during stage 1 are kept (no harm, just
unused) — useful audit trail.

## Open Questions

1. **Sync vs CDC** — see D2. Decide at promotion time after 6+ months
   more codebase context.
2. **Retention** — 90d default. Some compliance regimes require
   longer; check SOC2/PE-fund requirements at promotion time.
3. **Cross-org events?** — today every event is org-scoped. Is
   there ever a "platform-wide" event class (security alerts,
   maintenance notices)? Probably not, but worth a 2-minute think.
4. **Real-time push** — once events are persisted, we can subscribe
   via DynamoDB Streams or AppSync to push to the frontend. Out of
   scope here, but the events table makes it trivial later.
