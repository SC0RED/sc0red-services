# Proposal — Soft-Delete with Recovery (Phase 1: Tombstone + TTL)

## Why

Today every delete path in Janus is a hard delete. The bulk-delete UX
(`Delete N` with 5-second Toast Undo) catches the "oh wait, I noticed
immediately" reaction but offers no recovery for:

- A user on the wrong filter view who selects too many rows and clicks
  delete
- An admin housekeeping a portfolio who deletes the wrong scan
- An accidental click that the user doesn't notice for 10 minutes

Each Janus analysis represents 5–30 minutes of AI pipeline work plus
human review. A wrongly-deleted analysis is real cost (re-running the
pipeline) and real time (re-doing the review). Today the only recovery
is engineer-assisted DynamoDB restore from PITR — a "the building
burned down" tool, not a "user clicked wrong button" tool.

This proposal closes the gap by replacing hard deletes with **tombstone
soft-deletes**: a `deleted_at` attribute marks the record as deleted,
all reads filter it out, and a DynamoDB TTL attribute hard-evicts the
record after 90 days. Recovery in Phase 1 is via direct DynamoDB
update by an engineer; an admin self-serve UI is a separate later
phase.

The tombstone+TTL design was chosen over the alternatives in
`design.md` D1 — comparison and rationale documented there.

## What Changes

### Backend — write paths

- **`handle_delete_analysis`** — replace `company_repo.delete` and
  `assessment_repo.delete` calls with updates that set
  `deleted_at = now()` and `ttl = now() + 90d`. Same for the cascading
  scan delete: when an analysis was the last on its scan, the scan is
  tombstoned (not hard-deleted).
- **`handle_bulk_delete_analyses`** — same pattern, batched.
- **`handle_delete_scan`** — tombstone the scan and cascade-tombstone
  every linked company + their assessments + the scan→company link
  records.
- **Re-analyze flow** — when a worker writes a new assessment,
  tombstone the prior assessment instead of hard-deleting it. (Today
  the prior assessment is hard-deleted; this aligns the path.)
- **`scan_repo.unlink_company`** — tombstone the link record, not hard
  delete. Required so cascade-restore works (links must come back when
  a tombstoned analysis is restored).
- **Pipeline worker writes** — every `put_item` writes
  `created_at` (already done) plus an explicit `deleted_at: None` so
  the read filter has a stable shape.

### Backend — read paths

- **Repository layer** — every repo's `find_by_*`, `get_by_id`, and
  `get_by_ids` method filters out records where `deleted_at` is set.
  Filter applied centrally in repo wrappers, not in handlers.
- **`activity_handlers.py`** — projects can now emit `*_deleted`
  events, since tombstones are queryable. Carry-forward from
  `activity-events-table` D6.
- **`cleanup_orphan_scans.py`** — operates on tombstoned records the
  same as live ones; no behavioral change required (script reads the
  raw repo without filters, by design).

### Infrastructure

- **DynamoDB TTL attribute** — enable TTL on the `janus-{env}` table
  with `ttl` as the TTL attribute. CDK construct in
  `infrastructure/stacks/stack_resources.py:create_table`.
- **PITR remains enabled** — defense in depth. PITR covers
  catastrophic loss; tombstones cover user error.

### Frontend — no changes

The Toast Undo flow works exactly as today. The user sees the same
optimistic-removal UX. The 5s commit fires the same DELETE/POST
endpoints, but those endpoints now tombstone instead of hard-delete.

The only frontend-visible change is that `Recently Deleted` admin UI
is **NOT** in this phase — see "What we're not doing".

## Capabilities

### Modified Capabilities

- **`portfolio-streaming-results`** — analysis records can now exist
  in a tombstoned state; the streaming view filters them out.
- **`async-portfolio-scan`** — scan records can be tombstoned
  (cascade from analysis deletes); scan-status reads filter tombstones.
- **`failed-analysis-detail`** — a tombstoned analysis returns 404
  on the detail view (same as a hard-deleted one would have).
- **`activity-feed`** (existing tier-2 §5 spec) — opens the door to
  `*_deleted` event projection in a future change. Not implemented in
  this proposal.

### New Capabilities

None for Phase 1. A future Phase 2 would add a `recently-deleted`
capability with the admin self-serve recovery UI.

## What We're NOT Doing (Phase 2+ scope)

- **Admin "Recently Deleted" UI** — list filtered by 24h / 7d / 30d /
  90d, per-row Restore button, bulk-select restore. Defer until first
  user requests it; engineer-assisted recovery via direct DynamoDB
  update is the v1 path.
- **Cross-record relationship reconstruction** — if a scan is
  tombstoned and you restore one of its analyses, the scan stays
  tombstoned unless explicitly restored too. Restore is per-record
  in v1.
- **Audit log of deletions** — `deleted_at` + `deleted_by` on the
  record gives basic auditability; a separate audit log per
  compliance regime is out of scope.
- **`*_deleted` events in the activity feed** — once tombstones
  exist, the activity-handler projection can include them. Carry that
  forward to a follow-up change rather than bundling here.
- **Migration of existing hard-deleted records** — they're gone.
  Tombstones apply only to deletes that happen after this change
  ships. Pre-existing PITR coverage handles the historical case.
- **Cascade delete tightening** — if a parent scan is tombstoned but
  one of its analyses is restored, the analysis ends up "live but
  unreachable from a live scan." Acceptable for v1; document the
  edge case but don't auto-restore the scan.

## Impact

**Backend**:
- ~6 handler functions modified to tombstone instead of hard-delete
- ~4 repository read methods get a `WHERE deleted_at IS NULL` filter
  added centrally
- ~12 backend pytest cases need updating (current tests assert on
  hard-delete observation; new tests assert on tombstone state)
- New tests for "tombstoned record is invisible to reads",
  "TTL eviction is set 90 days out", "cascade tombstone on scan
  delete"

**Infrastructure**:
- One CDK change: enable TTL on the operational table. Re-deploys
  staging/testing/production. No data migration required (existing
  records without `ttl` simply never expire — same as today).

**Frontend**:
- No changes expected. Toast Undo works as-is. Bulk delete works
  as-is.

**Tests**:
- Backend pytest: ~12 modified + ~10 new. Coverage stays ≥ 95%.
- Frontend vitest: no changes expected.
- E2E: ensure existing delete-then-create-same-name flows still pass
  (tombstoned records shouldn't conflict with new records sharing
  attributes — they're invisible to all queries).

**Operational**:
- DynamoDB storage grows by tombstoned records for 90 days. At Janus
  volumes (hundreds per org) and item sizes (~10–50KB each) this is a
  rounding error.
- Repository read filters add a tiny CPU cost per query (one
  attribute check). Negligible.

**Migration / risk**:
- Zero data migration. The TTL attribute is opt-in per record; legacy
  records without it never expire (which is fine — they're live).
- Engineers MUST know that `deleted_at` is the new "is this gone?"
  signal, not absence of the record. Documented at the repo layer.

## Open Questions (resolve at apply time)

1. **`deleted_by` field?** — capture which user deleted the record.
   Useful for the Phase 2 admin UI ("Alice deleted these on Apr 27")
   and for compliance. Cheap to add now even though there's no
   consumer yet — same as `created_at` being added in §5 for the
   activity feed without an immediate user.

2. **TTL on the link records (`SCAN#{id}/COMPANY#{cid}`)?** — link
   records are small, but they accumulate. Decision: apply TTL to
   link records too, with the same 90-day window. Restore semantics:
   when an analysis is restored, the corresponding link record must
   also be restored (or recreated).

3. **Explicit restore endpoint vs in-band UPDATE?** — for v1,
   restoration is engineer-assisted; the engineer writes a direct
   `UPDATE deleted_at = NULL` via a DBA-style script. No new HTTP
   endpoint. Phase 2 brings the admin UI which would need the
   endpoint.

4. **Should `re-analyze` tombstone or hard-delete the prior
   assessment?** — alignment recommendation: tombstone, for
   consistency. But that means a re-analyzed company shows two
   assessments via the raw repo (one tombstoned, one live). The
   `find_by_company` filter at the repo level returns only the live
   one, so callers see the same shape as today.
