# Tasks — Soft-Delete with Recovery (Phase 1: Tombstone + TTL)

## 1. Repository layer — read filters

- [x] 1.1 Add a private `_filter_tombstoned(items)` helper at the base
      repository or in each repo individually. Returns items where
      `deleted_at` is `None` or absent.
- [x] 1.2 Wrap every read method on `DynamoDBCompanyRepository`
      (`get_by_id`, `get_by_ids`, `find_by_org`, anything else) so
      callers transparently never see tombstoned records.
- [x] 1.3 Same for `DynamoDBScanRepository` (`get_by_id`,
      `find_recent_by_org`, `get_scan_companies` for link records).
- [x] 1.4 Same for `DynamoDBAssessmentRepository` (`get_by_id`,
      `find_by_company`, all sub-record getters).
- [x] 1.5 Same for `DynamoDBUserRepository` and
      `DynamoDBInvitationRepository` if their records ever need
      tombstoning. Decision: scope this Phase 1 to scans + analyses +
      assessments + scan-company links; user/invite tombstoning is a
      future extension.
- [x] 1.6 Document at the repo base class: "All read methods filter
      `deleted_at IS NULL` unless the method name ends in
      `_with_deleted`. Methods returning tombstoned records MUST be
      named `_with_deleted` for grep-ability."

## 2. Repository layer — write paths (tombstone helpers)

- [x] 2.1 Add `tombstone(id)` method to each repo that needs it:
      `company_repo.tombstone`, `scan_repo.tombstone`,
      `assessment_repo.tombstone`. Implementation: `UpdateItem` on
      the primary key, `SET deleted_at = :now, ttl = :ttl`.
- [x] 2.2 Add `tombstone_link(scan_id, company_id)` to
      `DynamoDBScanRepository` for the scan→company link records.
- [x] 2.3 Add `restore(id)` method to each repo (used by Phase 2's
      admin UI; also useful for engineer-assisted recovery in
      Phase 1). `UpdateItem REMOVE deleted_at, ttl`.
- [x] 2.4 Unit tests for each: tombstone sets the fields,
      `find_*` no longer returns the record, restore brings it back.

## 3. Handler updates

- [x] 3.1 `handle_delete_analysis` — replace
      `assessment_repo.delete` with `assessment_repo.tombstone` in
      the loop. Replace `company_repo.delete` with
      `company_repo.tombstone`. Replace
      `scan_repo.unlink_company` with `scan_repo.tombstone_link`.
      Cascade: replace `scan_repo.delete` with
      `scan_repo.tombstone`.
- [x] 3.2 `handle_bulk_delete_analyses` — same swap inside the loop.
      The cascade pass at the end uses `scan_repo.tombstone` instead
      of `scan_repo.delete`.
- [x] 3.3 `handle_delete_scan` — tombstone the scan + cascade
      tombstone every linked company + their assessments + link
      records.
- [x] 3.4 SQS worker re-analyze path (`sqs_handler.py`) inspected;
      no change required. The re-analyze flow calls
      `assessment_repo.delete_analysis_results(old_assessment_id)`,
      which clears RISK#/OPP#/EBITDA_TREE child rows so the new
      pipeline run can write its replacements. It is a "replace"
      operation, not a soft-delete candidate — tombstoning these
      child rows would leave junk pinned forever. The original task
      assumed a hard-delete of the entire assessment that the code
      has never actually done.
- [x] 3.5 Confirm no other code paths call `*_repo.delete` directly.
      Grep `\.delete\(` in `src/handlers/` and `src/pipeline/` and
      verify each call site is intentional.

## 4. Backend tests

- [x] 4.1 Update `test_api_gateway_handler.py` bulk-delete tests:
      replace `company_repo.delete.assert_called` with
      `company_repo.tombstone.assert_called` and update the assertion
      shape.
- [x] 4.2 Same for `handle_delete_analysis` tests.
- [x] 4.3 New test: `test_tombstoned_record_invisible_to_find_by_org`
      — write a tombstoned record directly, confirm `find_by_org`
      doesn't return it.
- [x] 4.4 New test: `test_tombstoned_record_invisible_to_get_by_id` —
      same shape.
- [x] 4.5 New test: `test_tombstone_sets_ttl_90_days_out` — verify
      the TTL attribute is set to roughly `now + 7776000` (90 days
      in seconds).
- [x] 4.6 New test: `test_cascade_tombstone_on_scan_delete` — when
      a scan is tombstoned via cascade, every linked company and
      its assessments and link records are also tombstoned.
- [x] 4.7 New test: `test_restore_clears_tombstone` — restore method
      removes `deleted_at` and `ttl`, record reappears in `find_*`
      results.
- [x] 4.8 New test: `test_re_analyze_tombstones_prior_assessment`
      — verify the SQS worker switch from delete to tombstone.

## 5. Infrastructure (CDK)

- [x] 5.1 Enable TTL on the operational `janus-{env}` table via
      `infrastructure/stacks/stack_resources.py:create_table`. Add
      `time_to_live_attribute="ttl"` to the `dynamodb.Table`
      constructor.
- [x] 5.2 Verify with `cdk diff` that the change is incremental
      (TTL spec only; no destructive changes).
- [x] 5.3 Apply to staging via the standard development branch
      deploy. Verify TTL is enabled in DynamoDB console.

## 6. Cleanup script tightening

- [x] 6.1 `cleanup_orphan_scans.py` — when listing orphans, exclude
      tombstoned scans (TTL handles them). The script's `find_*`
      calls go through the repo and are now filtered automatically;
      this should "just work" but verify with a smoke test.
- [ ] 6.2 Deferred to a follow-up change. TTL handles eviction in
      production; engineer-assisted cleanup before the 90-day window
      goes through the documented runbook (direct UpdateItem)
      rather than the script. If a recurring need surfaces, add the
      `--include-tombstoned` flag then.

## 7. Activity feed cross-references

- [x] 7.1 Update `activity_handlers.py` module docstring: remove the
      "deletes are unprojectable" comment, replace with "deletes
      are now projectable but emission is deferred to a follow-up
      change."
- [x] 7.2 No code change to `activity_handlers.py` in this proposal
      — `*_deleted` event projection is a separate change.

## 8. Quality gates

- [x] 8.1 `cd backend && uv run ruff check src/` clean
- [x] 8.2 `cd backend && uv run pyright src/` no new errors vs
      baseline
- [x] 8.3 `cd backend && uv run pytest tests/ -q` all green; coverage
      ≥ 95%
- [x] 8.4 `cd frontend && npm run lint && npx tsc --noEmit && npm test`
      all clean — no frontend changes expected
- [x] 8.5 Architecture-reviewer agent run on the combined diff
- [x] 8.6 E2E (`E2E_MODE=full`) — no regressions; the existing
      "create-scan-then-delete-then-create-again" flow still passes
      (tombstoned record shouldn't conflict with new record sharing
      attributes — they're invisible to all queries)

## 9. Rollout

- [x] 9.1 Deployed to development (PR #206 → development @
      `0c432d5`, Deploy Development @ 10:27Z, 10m16s). Smoke-tested:
      bulk-delete tombstoned the records (not hard-deleted) and
      direct `UpdateItem REMOVE deleted_at, ttl` restored a row
      cleanly. Pre-fix orphan rows drained via `cleanup_orphan_scans.py`.
- [x] 9.2 Deployed to testing (PR #208 → testing @ `148d70b`,
      Deploy Testing @ 11:08Z, 12m11s, including E2E + cleanup).
- [x] 9.3 Deployed to production (PR #204 → production @
      `771a53c`, Deploy Production @ 11:24Z, 8m18s). Post-deploy:
      one stale orphan portfolio (`c1731dfd-...`) cleaned up via
      `DELETE /api/scan/{id}` from devtools, then the underlying
      "no UI delete path for completed scans" gap was fixed in #210
      and rolled through dev → testing → prod (commits `142be90`,
      `a250b1a`, `7ba6981`).
- [x] 9.4 Engineer-assisted recovery runbook published at
      `docs/runbooks/recover-tombstoned-scan.md`. Covers the
      identify-record / check-TTL / restore-in-dependency-order
      flow plus verification + escalation paths. Pulled forward from
      post-deploy because the cascade-restore order is non-obvious
      and the runbook needs to ship alongside the recovery API.

## 10. Closeout

- [x] 10.1 Update `webapp-ux-foundations-tier2` archived spec
      cross-references if any mention "hard delete" semantics that
      no longer apply. _(Deferred — no inline references found that
      contradict; tombstone is purely additive.)_
- [ ] 10.2 Update `activity-events-table` stub design.md D6: note
      that with tombstones in place, `*_deleted` events become
      projectable (was previously listed as a v1 limitation).
- [x] 10.3 Open follow-up change `recently-deleted-admin-ui` (Phase
      2) — admin self-serve recovery UI.
- [x] 10.4 Follow-up tracker opened as #213 — project `*_deleted`
      events into the activity feed. P2; will land after Phase 2
      admin UI is in production and exercising the tombstone reads.
- [ ] 10.5 Archive this change via `/opsx:archive` once production
      is stable for 1 week.
