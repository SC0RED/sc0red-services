# Tasks — Activity Events Table Migration

> **STUB.** All tasks below are deliberately unticked. Do NOT start
> until at least one trigger condition from `proposal.md` fires.
>
> When promoted: re-validate `design.md` against the current
> codebase, pick the backfill option (D6), then expand each section
> below with concrete subtasks and run `/opsx:apply`.

## 0. Pre-flight (at promotion time)

- [ ] 0.1 Re-read `proposal.md` and `design.md`. Mark which
      assumptions still hold and which need updating.
- [ ] 0.2 Pick the backfill option (D6 in `design.md`):
      A=events-start-now, B=synthetic backfill, C=Streams CDC.
- [ ] 0.3 Decide sync-write vs CDC for handler integration (D2).
      Default: sync.
- [ ] 0.4 Confirm retention (D5). Default: 90 days TTL.
- [ ] 0.5 Snapshot the `activity_feed.company_page_capped` warning
      counts so we have a before/after metric for the migration.

## 1. Infrastructure

- [ ] 1.1 New CDK construct for `janus-events-{env}` DynamoDB table
      (PK/SK + GSI1, PITR enabled, TTL on `ttl` attribute).
- [ ] 1.2 IAM grants: API Lambda reads/writes; worker Lambda writes;
      no other services touch it.
- [ ] 1.3 `cdk synth` clean; `cdk diff` against staging matches
      expectations.
- [ ] 1.4 Wire env var `ACTIVITY_EVENTS_TABLE` into the API Lambda
      and any worker that writes events.

## 2. Backend — repository + model

- [ ] 2.1 New `backend/src/models/events.py` — Pydantic
      `ActivityEvent` model + per-event-type subclasses (or single
      union with discriminator on `type`).
- [ ] 2.2 New `backend/src/repositories/dynamodb/events_repository.py`
      with `put`, `find_by_org(org_id, limit, cursor)`, `delete_by_id`
      (rare, for retraction).
- [ ] 2.3 Repository unit tests covering put + cursor pagination
      edge cases.

## 3. Backend — write-path integration

- [ ] 3.1 `scan_handlers.handle_scan_start` → write `scan_started`
- [ ] 3.2 `scan_handlers.handle_delete_scan` → write `scan_deleted`
- [ ] 3.3 `sqs_handler` (status flip to complete) → write
      `scan_completed`
- [ ] 3.4 `sqs_handler` (status flip to failed) → write
      `scan_failed`
- [ ] 3.5 `analysis_handlers.handle_delete_analysis` → write
      `analysis_deleted`
- [ ] 3.6 Pipeline completion (wherever `analyzed_at` is set) →
      write `analysis_completed`
- [ ] 3.7 Pipeline failure handler → write `analysis_failed`
- [ ] 3.8 `invitation_handlers.handle_invite_member` →
      write `member_invited`
- [ ] 3.9 `auth_handlers.handle_register` → write `member_joined`
- [ ] 3.10 Each write-path: failure must not block the operational
      action. Log a warning and continue.
- [ ] 3.11 Integration tests for each write-path using LocalStack +
      a real DynamoDB stub.

## 4. Backend — read-path cutover

- [ ] 4.1 Implement `activity_handlers.handle_get_activity` v2 — query
      events table directly with cursor pagination.
- [ ] 4.2 Feature flag `ACTIVITY_FEED_USE_EVENTS_TABLE` env var
      toggles v1 (projection) vs v2 (table). Default false until
      stage 2.
- [ ] 4.3 Update `EventType` Literal to include the new event types
      (`scan_completed`, `scan_failed`, `scan_deleted`,
      `analysis_failed`, `analysis_deleted`).
- [ ] 4.4 Update frontend `ActivityEventType` union to match (parity
      check `check_activity_event_type_parity.py` will fail until
      both sides agree — that's the point).
- [ ] 4.5 Update frontend `buildTargetHref` to route the new event
      types appropriately (`*_deleted` likely render as plain rows,
      no link).

## 5. Backfill (executed once, per chosen option from 0.2)

- [ ] 5.1 If option A: nothing — feed starts empty on deploy day.
- [ ] 5.2 If option B: write `scripts/backfill_activity_events.py`
      that walks existing scan/company/user/invitation records and
      emits equivalent events. Run once per environment. Document
      the limitations baked into the synthetic events.
- [ ] 5.3 If option C: enable DynamoDB Streams on the operational
      table; deploy projector Lambda; let it run for a 24h window
      to catch up.

## 6. Decommission v1 projection

- [ ] 6.1 Delete the four `_project_*` helpers in
      `activity_handlers.py`.
- [ ] 6.2 Delete `_MAX_EVENTS` and the cap-hit warning log.
- [ ] 6.3 Delete the v1 limitations section from the handler
      docstring.
- [ ] 6.4 Delete the corresponding caplog tests in
      `test_activity_handlers.py`.
- [ ] 6.5 Delete the feature-flag toggle once stage 2 is stable in
      production (target: 2 weeks after stage 2 ships).

## 7. Quality gates

- [ ] 7.1 `cd backend && uv run ruff check src/` clean
- [ ] 7.2 `cd backend && uv run pyright src/` no new errors
- [ ] 7.3 `cd backend && uv run pytest tests/ -q` all pass; coverage
      ≥ 95%
- [ ] 7.4 `cd frontend && npm run lint && npx tsc --noEmit && npm test`
      all clean
- [ ] 7.5 Architecture-reviewer agent run on the combined diff
- [ ] 7.6 E2E (`E2E_MODE=full`) — no regressions; new test
      asserting an event appears in the feed end-to-end after a
      scan completes
- [ ] 7.7 `check_activity_event_type_parity.py` clean — backend
      and frontend agree on the new event types

## 8. Rollout

- [ ] 8.1 Stage 1 (write-only) deploy to development. Observe for
      48h that events are accruing.
- [ ] 8.2 Stage 1 to testing. Observe.
- [ ] 8.3 Stage 1 to production. Observe for one week.
- [ ] 8.4 Stage 2 (read cutover) to development with feature flag
      enabled. Compare v1 vs v2 outputs for parity.
- [ ] 8.5 Stage 2 to testing.
- [ ] 8.6 Stage 2 to production.
- [ ] 8.7 Decommission tasks from §6 once stage 2 is stable for
      2 weeks.

## 9. Closeout

- [ ] 9.1 Update `webapp-ux-foundations-tier2` archive notes if any
      cross-references need updating (likely none — that change is
      already archived by the time this lands).
- [ ] 9.2 Update `docs/api.md` with the new `/api/activity` semantics
      (cursor pagination is real now).
- [ ] 9.3 Add a CloudWatch dashboard widget for events-table size
      and write rate.
- [ ] 9.4 Archive this change via `/opsx:archive` once production is
      stable.
