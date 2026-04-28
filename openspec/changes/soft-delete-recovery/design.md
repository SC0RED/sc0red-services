# Design — Soft-Delete with Recovery (Phase 1: Tombstone + TTL)

## Context

Hard-delete is the wrong default for Janus's primary work product
(analyses, scans, assessments — each a multi-step AI pipeline result
that the user reviewed). The 5-second Toast Undo catches reflexive
"oh wait" reactions but doesn't catch:

- "I selected too many" (noticed minutes later)
- "I was on the wrong filter" (noticed hours later)
- "An admin housekeeping mass-deleted, didn't notice for a week"

Today the only recovery path is engineer-assisted DynamoDB PITR
restore, which is per-table not per-record — useful for catastrophic
loss, useless for granular user error.

## v1 (today) vs v2 (this proposal)

```
                  v1 (hard delete)
                  ────────────────────
   handle_delete_analysis(id):
       company_repo.delete(id)         ── DynamoDB DeleteItem
       assessment_repo.delete(...)     ── DynamoDB DeleteItem
       scan_repo.unlink_company(...)   ── DynamoDB DeleteItem
       (cascade) scan_repo.delete()    ── DynamoDB DeleteItem
       
       Recovery: PITR table-level restore. No per-record path.
```

```
                  v2 (tombstone + TTL)
                  ────────────────────
   handle_delete_analysis(id):
       company_repo.tombstone(id)       ── UpdateItem SET
                                            deleted_at, ttl
       assessment_repo.tombstone(...)   ── UpdateItem SET
                                            deleted_at, ttl
       scan_repo.unlink_company_ts(...) ── UpdateItem on link record
       (cascade) scan_repo.tombstone()  ── UpdateItem on scan
       
   All reads filter `deleted_at IS NULL` at repo layer.
   DynamoDB TTL evicts the record 90 days after `deleted_at`.
   
   Recovery: UpdateItem REMOVE deleted_at, ttl
             (engineer-assisted in v1; admin UI in Phase 2)
```

## Decisions

### D1. Tombstone-in-place, NOT separate archive table or S3 archive

**Decision:** mark the record with `deleted_at` on the same item, in
the same DynamoDB table. Filter in reads. Use DynamoDB TTL for
automatic eviction after 90 days.

**Why over S3 archive:** S3 archive (PUT to S3 → DELETE from DynamoDB)
adds a two-stage move with partial-failure modes (archive PUT
succeeds, main DELETE fails → record in two places). Cross-record
relationships (analysis ↔ scan ↔ assessment) make restoration
brittle — re-keying on restore must reassemble the chain. Tombstones
keep relationships intact: the foreign-key shape never changes, the
records are just hidden.

**Why over a separate archive table (sync move):** same partial-
failure issue plus an extra DynamoDB write per delete. No clear win
over tombstoning.

**Why over Stream-driven hybrid (move on UPDATE deleted_at):**
elegant but more moving parts (Stream + Lambda + DLQ + monitoring)
than the value at this scale. The hybrid becomes attractive when the
events-table migration in `activity-events-table` triggers — at that
point a Stream subscriber exists for other reasons and can absorb
archival cheaply. Staying in tombstone-in-place v1 doesn't paint the
codebase into a corner.

**Trade-off accepted:** every read query needs a `WHERE deleted_at
IS NULL` filter. Mitigation: applied at the repository layer (one
wrapper per repo), not at handler level. Bug surface bounded.

### D2. `deleted_at` is an ISO 8601 string, not a boolean

**Decision:** the tombstone marker is `deleted_at: str | None` (ISO
8601 timestamp), not `is_deleted: bool`.

**Why:** carries the timestamp inline; future audit queries
("everything deleted in the last 24h") trivially work. Boolean would
require a paired `deleted_at` field anyway.

### D3. TTL attribute is `ttl` (epoch seconds), set to `deleted_at + 90 days`

**Decision:** add a `ttl` attribute to tombstoned records, set to
the epoch-seconds value 90 days past `deleted_at`. Configure
DynamoDB TTL on the table to use this attribute.

**Why:** automatic hard-delete with no cron job. DynamoDB TTL is
free, has no Lambda surface, and runs lazily within ~48 hours of the
TTL timestamp. Late eviction by 1–2 days is fine for our case.

**Why not on the same `deleted_at` field:** DynamoDB TTL needs a
numeric epoch value; ISO 8601 string isn't usable. Separate `ttl`
attribute is the standard pattern.

### D4. Read filter at the repository layer, not the handler layer

**Decision:** every `find_*`, `get_by_id`, `get_by_ids` repo method
adds a `deleted_at IS NULL` filter (or post-fetch list comprehension
where DynamoDB FilterExpressions don't apply). Handlers don't know
about tombstones at all.

**Why:** centralizes the bug surface. A new handler that uses an
existing repo method is automatically safe. New repo methods are the
only place the rule must be remembered.

**Why not at the table-client layer:** too aggressive. Some callers
(e.g., the cleanup script, a future admin recovery UI, audit
queries) need to see tombstoned records. Push the filter up so it
can be opt-out at the repo method level if a recovery path is added.

**Mitigation for the bug surface:**
- A unit test pattern: every `find_*` method gets a "filters out
  tombstoned records" test.
- A pyright assertion: tombstoned-aware methods named `_with_deleted`
  or similar so usage is grep-able.
- An ADR-style note in the repo base class: "all read methods filter
  tombstones unless documented otherwise."

### D5. Cascade tombstone propagates the same way as cascade delete

**Decision:** when a scan is tombstoned (because its last analysis
was just tombstoned), every linked company → its assessments → its
scan-company link records get tombstoned too. Same cascade as today's
hard-delete path.

**Why:** preserves the invariant "if a scan is invisible, its child
analyses are invisible." Without this, a tombstoned scan would still
have visible child analyses orphaned from any scan view.

**Restore semantics:** restoring a tombstoned analysis from the
admin recovery UI (Phase 2) does NOT auto-restore the parent scan.
The restored analysis is reachable directly via `/analysis/{id}`
but appears as "scan: deleted" in any UI cross-reference. Documented
edge case; revisit in Phase 2 if confusing.

### D6. `re-analyze` tombstones the prior assessment instead of hard-deleting

**Decision:** the SQS worker's "delete old assessment after writing
new one" path becomes a tombstone. Aligns with the rest of the
codebase and gives a recovery path if a re-analysis was wrong.

**Why:** consistency. If every other delete is a tombstone, having
one path that hard-deletes is a special case waiting to bite us.

**Trade-off:** every re-analyzed company accumulates a tombstoned
prior assessment for 90 days. At ~5KB per assessment + N
re-analyses per company, this is rounding-error storage cost.

### D7. Engineer-assisted recovery in Phase 1, admin UI deferred

**Decision:** Phase 1 ships the tombstone mechanism + TTL eviction.
Recovery is via direct DynamoDB `UpdateItem REMOVE deleted_at, ttl`
from a DBA-style script. No new HTTP endpoint, no admin UI.

**Why:** ship safety today, build self-serve when there's evidence
someone needs it. The admin UI is a non-trivial UX surface (filters,
bulk-restore, permissions, undo-of-undo) that doesn't deserve to
block the data-safety win.

**Phase 2 (separate change):** `recently-deleted-admin-ui`
capability — admin-only `/settings/recently-deleted` page,
time-window filters, per-row Restore button, bulk Restore. Drives
the design of an explicit `POST /api/admin/restore` endpoint.

### D8. Existing PITR remains enabled (defense in depth)

**Decision:** don't disable PITR on the production table. Tombstones
cover user-error recovery; PITR covers catastrophic loss
(corruption, malicious deletion bypassing the handlers, accidental
table drop).

**Why:** layered defense costs almost nothing — PITR is enabled
once at the CDK level. Removing it has no upside.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| **Forgotten read filter on a new repo method** — tombstoned record leaks into a UI surface | Unit test pattern enforces "find filters out tombstones"; lint rule could flag direct `client.query` calls in handlers (defer until first incident) |
| **TTL eviction lag (up to 48h after timestamp)** — restoration window in practice is 88-90 days, not exactly 90 | Document; users don't notice; restore window remains generous |
| **Storage growth from tombstones** | Bounded at 90 days × deletion rate; rounding error at Janus scale |
| **Re-analyze accumulates tombstoned old assessments** | Same — bounded; storage cost is negligible |
| **DynamoDB TTL is non-deterministic** — can't rely on records being gone at exactly +90d | If we ever need precise eviction (e.g., GDPR right-to-be-forgotten window), add an explicit cron in Phase 3 |
| **Cascade-restore confusion** — scan stays tombstoned when child analysis is restored | Phase 2 admin UI calls this out clearly; Phase 1 has no recovery UI so risk is dormant |

## Migration Plan

Two-stage rollout to keep rollback easy:

**Stage 1 — write side (tombstone instead of delete):**
1. Add `deleted_at` and `ttl` filter at every repo read method
2. Add tombstone helpers to repos
3. Switch handlers to call `tombstone` instead of `delete`
4. Re-deploy. Backward-compatible — existing records have no
   `deleted_at`, so they pass the read filter trivially.

**Stage 2 — TTL on the table:**
1. Enable DynamoDB TTL via CDK
2. Re-deploy infrastructure
3. Existing records without `ttl` are unaffected (TTL only acts on
   records that have the attribute). Future tombstones get evicted
   90 days after creation.

The two stages can ship in one PR — they're independent.

**Rollback:** revert the handler changes. Existing tombstoned
records remain in place (no data loss), but new deletes become hard
again. The `ttl` attribute on tombstoned records continues to evict
them on schedule — no orphan data.

## Open Questions (resolve at apply time)

1. **Should `unlink_company` tombstone the link record or hard
   delete it?** — Tombstone, to preserve restorability. But this
   means tombstoned link records accumulate alongside tombstoned
   companies. Negligible cost.

2. **Should the bulk-delete cleanup script (`cleanup_orphan_scans.py`)
   be aware of tombstones?** — Yes. The script should distinguish:
   - Hard-deletable orphans (should be hard-deleted immediately by
     the script)
   - Tombstoned scans (let TTL handle them; script logs but doesn't
     touch)
   The current script uses raw repo reads (no filter), so it sees
   everything. Decision: treat tombstoned scans as "expected" —
   skip them silently.

3. **Should the activity feed start projecting `*_deleted` events
   once tombstones exist?** — Probably yes, in a follow-up change.
   Outside the scope of this proposal; cross-references the
   `activity-events-table` stub.

4. **What happens during Phase 2 if a user tries to restore a
   tombstoned record whose parent has been hard-evicted (>90d
   gone)?** — Restore should fail with a clear message. Phase 2 UI
   handles this; Phase 1 doesn't have the path.
