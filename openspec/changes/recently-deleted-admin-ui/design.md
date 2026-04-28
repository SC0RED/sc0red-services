# Design — Recently Deleted (Phase 2 of Soft-Delete with Recovery)

## Context

Phase 1 (`soft-delete-recovery`) makes deletes recoverable for 90 days
via tombstones + DynamoDB TTL. Phase 1's recovery path is engineer-
assisted (direct DynamoDB UpdateItem). That's safe-but-slow: a wrong
delete still requires paging an engineer, finding the record id,
running an UpdateItem, and explaining the situation.

This phase adds the self-serve UI: an admin user opens
`/settings/recently-deleted`, picks a time window, sees what was
deleted, clicks Restore. End to end, no engineer.

```
                   USER FLOW
                   ─────────────────────────────────

   1. Admin notices a wrong delete on Monday
                ↓
   2. Goes to Settings → Recently Deleted
                ↓
   3. Filters by "Last 7 days"
                ↓
   4. Spots the wrongly-deleted records, ticks them
                ↓
   5. Clicks "Restore N"
                ↓
   6. Toast: "Restored N records"
                ↓
   7. Records reappear in Recent Scans / /analyses
```

## Goals / Non-Goals

**Goals:**
- Self-serve recovery for admin users within 90 days of any delete
- Time-window filtering (24h / 7d / 30d / 90d) so the page doesn't
  drown in noise
- Cross-record awareness: when restoring an analysis whose parent
  scan is also tombstoned, surface the option to restore both
- Bulk-restore for housekeeping ("we accidentally deleted 30
  analyses last week; restore them all in one go")
- Role-gated: analysts don't see the page or the routes

**Non-Goals:**
- Permanent delete from the UI — TTL handles eviction
- Cross-org impersonation — admins recover their own org only
- Restore preview / diff — restore is atomic, no preview needed
- Audit log surface — CloudWatch logs cover it; persistent audit
  table is a compliance-driven separate change
- Restoring records older than 90 days — TTL has evicted them

## Decisions

### D1. Backend lives under `/api/admin/*` with a role check

**Decision:** new HTTP routes are `GET /api/admin/recently-deleted`
and `POST /api/admin/restore`. Both check
`authentication.role === 'admin'` at the handler boundary; non-admins
get 403.

**Why the `/admin/` namespace:** clearly separates admin-only routes
from end-user routes. Future admin features (audit log surface,
team usage stats, impersonation tools) land under the same prefix
with the same role check.

**Why role check at the handler, not the router:** the router does
auth (verifies the token); role-based authorisation is a handler
concern. Keeps the router thin and lets us add per-handler role
nuance later (e.g., "analyst can see their own deletes but not
team's").

### D2. Single restore endpoint takes mixed record types

**Decision:** `POST /api/admin/restore` body is `{ ids: [...] }`.
The backend infers each id's type by attempting `get_by_id_with_deleted`
on each repo (company first, then scan); whichever matches is the
record's type.

**Why one endpoint, not two:** the UI needs to bulk-restore mixed
types in one click ("restore these 3 analyses + their parent scan").
Splitting into `POST /restore-analyses` + `POST /restore-scans`
would force the UI to issue two requests and reconcile, with all
the partial-failure complexity that's exactly what we fixed in the
bulk-delete cascade work (#199).

**Why type inference, not requiring `[{id, type}]` from the client:**
the client already shows the types in the list (it has them from
the `recently-deleted` GET response). Asking the client to
re-attach them on the restore request is busywork. The backend
already has to look up the record to validate org access, so
inferring type is one extra read per id — negligible.

### D3. List response shape is denormalised, not stitched client-side

**Decision:** `GET /api/admin/recently-deleted` returns each record
with `displayName`, `deletedBy.name`, `parentTombstoned: bool`
already filled in. Backend resolves user names + parent-scan
tombstone state before returning.

**Why:** the alternative is the client making N follow-up requests
(or a /users batch read) to resolve actor names. Denormalising at
read time keeps the client trivial — render the array, no joining
required.

**Cost:** one user-batch lookup per listing call. At admin volumes
(handful of admins per org, page accessed occasionally), trivial.
The N+1 lookup for `parentTombstoned` is bounded by the number of
analyses in the window — also bounded.

### D4. Cascade behaviour: surface it in the UI, do NOT auto-resolve

**Decision:** when an admin restores an analysis whose parent scan
is tombstoned, the UI shows a warning and a checkbox "Also restore
parent scan." The backend does NOT auto-restore the parent — it
follows the request payload literally.

**Why:** auto-restore violates the principle of least surprise.
"I clicked one button and 5 records came back" feels magical;
"I clicked one button and 1 record came back, and the UI told me
the parent is also gone" is honest. The admin can re-tick and
re-Restore in 2 seconds.

**UI shape:** when `parentTombstoned: true`, render an inline pill
on the row: "⚠ Parent scan also deleted". On Restore click, the
modal/toast asks: "Also restore parent scan? [Yes / No]". `Yes` adds
the scan id to the request payload.

### D5. No optimistic UI for restore; just a Toast on success

**Decision:** clicking Restore immediately fires the request. While
in-flight, show a Toast loading variant. On success, show a success
Toast and refetch the list. On failure, show error Toast; the row
stays in the list.

**Why no optimistic-remove like delete:** restore is the inverse of
delete. Optimistic-remove from the Recently Deleted list would feel
weird — the user wants to see the record vanish from the deleted
list AND reappear elsewhere. The success Toast + refetch handles
both, and a small (sub-second) flicker before the row disappears is
honest.

**Why no Toast Undo:** restore is non-destructive. There's nothing
to undo — if the admin wants to delete again, they go through the
normal delete flow.

### D6. Time windows are server-evaluated, not client-evaluated

**Decision:** the `?window=24h|7d|30d|90d` query param is parsed
server-side. The server filters records where
`deleted_at >= now() - window`. Client doesn't see records outside
the window at all.

**Why:** keeps the payload small. At default 30d the response might
be 50-200 records; at 90d 500-1500. The client filtering case
("send everything, filter on the client") wastes bandwidth and
forces the GSI to scan more than it needs.

**Implementation:** repo method
`find_tombstoned_by_org(org_id, window_start)` filters at the
DynamoDB layer when possible (e.g., GSI on `deleted_at` if we add
one) or in-memory after fetch when not. At our scale, in-memory
filter is fine; revisit if a GSI helps. Tasks.md tracks this.

### D7. Bulk-restore reuses the existing `BulkActionsBar` component

**Decision:** the `BulkActionsBar` from tier-2 §3 (currently used
on `/analyses` for Delete N + Compare N) extends to support a
"Restore N" action via a prop. No second component needed.

**Why:** consistency. Same checkbox column pattern, same shift-
click range select, same sticky-bar UX. The only difference is the
primary action label.

**Implementation:** `BulkActionsBar` already takes `onDelete` +
`compareHref`. Add `onRestore?: () => void` and `restoreLabel?: string`
props. When provided, renders a Restore button instead of (or
alongside) Delete. The Recently Deleted page passes `onRestore` and
no `onDelete`.

**Slight tension:** the component now branches on which action it
renders. Acceptable while we have one consumer per action. If a
future surface wants both (unlikely), refactor to take an `actions`
array.

### D8. Engineer-assisted recovery path remains

**Decision:** the direct-DynamoDB UpdateItem approach from Phase 1
remains valid. The admin UI is an additional path, not a
replacement. Engineers retain the ability to restore cross-org
records (e.g., for support tickets) via the same tooling.

**Why:** belt-and-braces. The UI is fine for normal cases; the
direct path is the escape hatch when the UI itself is broken or
the admin is locked out.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| **Admin role escalation** — a malicious analyst gains access to admin role and bulk-restores stuff they shouldn't | Role check on every handler; org-scoped (can't reach other orgs). Compromised admin is a separate threat model already covered by Cognito session expiry + audit logs. |
| **Restore-of-restore loop** — admin restores, deletes, restores, deletes... | Tombstones are overwritten on each delete. No accumulation, no loop danger. |
| **Parent-scan-evicted edge case** — admin tries to restore an analysis whose parent scan was hard-evicted by TTL | Backend returns `ttl_expired` in `failed` array; UI surfaces "Parent no longer exists, restored without scan link." Documented in Phase 1 design D5. |
| **Stale list during restore** — admin sees record, clicks Restore, but TTL just evicted it | Backend's `get_by_id_with_deleted` returns nothing → `failed: ttl_expired`. UI re-fetches list to drop the row. Edge case; user sees clean error. |
| **Concurrent restores from two admin tabs** | Restore is idempotent — clearing `deleted_at` on a record that's already cleared is a no-op. Race is benign. |
| **Bulk-restore with N=100+** | DynamoDB BatchWrite isn't applicable (we need per-item updates). N parallel UpdateItem calls; bounded by admin selection size. Acceptable. |

## Migration Plan

This change has no data migration. It surfaces existing tombstoned
records the moment Phase 1 is in place.

**Rollout sequence:**

1. **Phase 1 ships first** (`soft-delete-recovery`). Until that
   lands there's nothing to surface — no records are tombstoned.
2. **Phase 2 ships next** (this change). Frontend route +
   backend endpoints land together. Admin role check guards
   visibility on day 0.
3. **Verify on dev:**
   - Delete an analysis as a non-admin → log in as admin → see it
     in Recently Deleted → restore → verify it reappears on
     `/analyses`.
   - Delete a scan with multiple analyses → all surface in
     Recently Deleted with parent-tombstoned indicators.

**Rollback:**
- Remove the sidebar entry (admin can't reach the page from the
  UI). Backend endpoints remain but require admin role + valid
  session, so risk is bounded.
- Hard rollback: revert the PR. No data lost.

## Open Questions

1. **Should the page show records deleted by analysts or only by
   admins?** — Show all org-scoped tombstoned records regardless of
   actor role. The admin acts as the org's recovery operator.

2. **Should we surface "restore" vs "permanent delete" actions
   together on this page?** — No; permanent delete is out of scope
   for v1 (TTL handles eviction). Adding a manual hard-delete
   button is a separate change with confirmation-UX considerations.

3. **Pagination?** — Bounded at 90d × deletion rate. At expected
   volumes (a few hundred records max per org per 90d window), no
   pagination needed. If a customer hits the cap we add cursor-based
   paging in a small follow-up.

4. **Search?** — Client-side substring filter on `displayName`.
   Trivial, useful when the list is long. Not server-side search.

5. **Restoring a tombstoned scan whose linked companies were
   hard-deleted before the tombstone existed (pre-Phase 1 records)?**
   — Restore the scan record; companies that were already hard-gone
   stay gone. Same as the `parent_tombstoned: true` UX surface in
   reverse — the UI doesn't need to call this out specially.
