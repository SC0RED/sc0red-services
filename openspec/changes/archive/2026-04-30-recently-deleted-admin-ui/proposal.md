# Proposal — Recently Deleted (Phase 2 of Soft-Delete with Recovery)

## Why

`soft-delete-recovery` (Phase 1) ships the tombstone + TTL mechanism
that makes deletes recoverable for 90 days. But Phase 1 has no
self-serve recovery path — it's engineer-assisted via direct DynamoDB
`UpdateItem`. That's adequate for "the data is safe" but not for "an
admin notices a wrong delete on Monday morning and wants the records
back without paging an engineer."

This proposal adds a self-serve admin UI:

- A `/settings/recently-deleted` page (admin-only, gated by role)
- Time-window filter (24h / 7d / 30d / 90d)
- List of tombstoned records with metadata (source URL, type,
  deleted-by, deleted-when)
- Per-row Restore button
- Bulk-select Restore for multi-record recovery
- Cross-record awareness: when restoring an analysis whose parent
  scan is also tombstoned, surface the parent and offer to restore
  both

The whole thing is scoped to **admin users only** (`role === 'admin'`
on the user record). Analysts don't see the page or the routes.

## What Changes

### Backend

- **New `GET /api/admin/recently-deleted?window=24h|7d|30d|90d`** —
  returns tombstoned records for the user's org within the window.
  Default window: `30d`. Max window: `90d`. The user-facing window
  stays 90 days even though the underlying TTL is 95 days (5-day
  internal margin to eliminate the same-session eviction race —
  see design D9).
  Authorisation: admin role required; returns 403 otherwise.
  Response shape:

  ```jsonc
  {
    "records": [
      {
        "id": "...",
        "type": "analysis" | "scan",
        "displayName": "Acme Corp",      // company_name for analyses;
                                          // source_url for scans
        "scanId": "...",                  // present on analyses;
                                          // null for standalone scan parents
        "deletedAt": "2026-04-25T18:00:00Z",
        "deletedBy": { "id": "user-1", "name": "Alice" },
                                          // null when actor unknown
        "parentTombstoned": false,        // true if this is an analysis
                                          // whose parent scan is also
                                          // tombstoned (UI surfaces a
                                          // "restore parent too?" hint)
      },
      ...
    ]
  }
  ```

  Records are sorted newest-deleted-first.

- **New `POST /api/admin/restore`** — body `{ ids: [...] }` (mixed
  scans and analyses; backend infers each record's type). Atomically
  restores every requested record by clearing `deleted_at` and
  `ttl`. Cascade behaviour:

  - Restoring a **scan** does NOT auto-restore its tombstoned child
    analyses (admin must select them too if desired). Documented in
    the UI as "Restoring this scan does not bring back its
    analyses — they need to be restored separately."
  - Restoring an **analysis** whose parent scan is tombstoned does
    NOT auto-restore the parent. The UI offers a checkbox "Also
    restore parent scan" that, when ticked, includes the parent in
    the request payload.

  Authorisation: admin role required.

  Response shape:

  ```jsonc
  {
    "restored": ["id-1", "id-2"],
    "failed": [{"id": "id-3", "reason": "not_found" | "ttl_expired"}]
  }
  ```

- **Repository layer** — new `_with_deleted` variants of key read
  methods (per the Phase 1 design D4 naming convention):
  `company_repo.find_tombstoned_by_org(org_id, window_start)`,
  `scan_repo.find_tombstoned_by_org(org_id, window_start)`,
  `*_repo.get_by_id_with_deleted(id)` for the restore path.

- **Restore handler** — repos already have `restore(id)` from Phase 1.
  This change wires a new `handle_admin_restore` handler that
  validates each id, applies role check, calls `restore` on the
  appropriate repo per record type, and returns the `{restored,
  failed}` payload.

### Frontend

- **New route** `frontend/src/app/(authenticated)/settings/recently-deleted/page.tsx`
  — server component that fetches the list via `backendFetch`,
  passes it to a client component for interactivity. Linked from the
  Settings sidebar (existing route added in Tier 1 §4).

- **New client component** `RecentlyDeletedView.tsx`:
  - Time-window chips (24h / 7d / 30d / 90d) — default 30d
  - Search box (filter by displayName) — client-side over the
    loaded slice
  - Table of records with checkbox column, displayName,
    type badge (analysis / portfolio scan / standalone scan),
    deleted-by, deleted-at (uses existing `<RelativeTime>`)
  - Sticky bottom `<BulkActionsBar>` (reuses the existing component
    from Tier 2 §3) when ≥ 1 selected — shows "Restore N"
  - Per-row Restore button (single-record path)
  - "Parent scan also deleted" badge on analyses whose
    `parentTombstoned: true`, with hover tooltip
  - On Restore: optimistic remove from the list + Toast success.
    On commit: POST to `/api/admin/restore`. On failure: restore
    the row and Toast error.
  - Empty state when no records in window: "No deletions in the
    last {window}. Tombstoned records expire from this list 90 days
    after deletion."

- **New API proxy route**
  `frontend/src/app/api/admin/recently-deleted/route.ts` — GET only,
  forwards to backend.

- **New API proxy route**
  `frontend/src/app/api/admin/restore/route.ts` — POST only,
  forwards to backend.

- **Sidebar** — add "Recently Deleted" entry under Settings,
  visible only when `session.user.role === 'admin'`.

### Permissions

- Backend handlers: every `/api/admin/*` route asserts
  `authentication.role === 'admin'`. Returns 403 for analysts.
- Frontend route: server component checks session role; renders 404
  for non-admins (don't surface the page's existence). The sidebar
  link is also hidden for analysts.

## Capabilities

### New Capabilities

- **`recently-deleted`** — admin-only surface for browsing and
  restoring tombstoned records. Frontend page + two backend
  endpoints + sidebar entry.

### Modified Capabilities

- **`user-settings`** (existing tier-1 §4 spec) — Settings sidebar
  gains a new entry, gated by admin role.
- **`bulk-actions`** (existing tier-2 §3 spec) — `BulkActionsBar` is
  reused; minor extension to support a "Restore" action label
  alongside its existing Delete.

## Impact

**Backend**:
- 2 new HTTP routes, 1 handler module (`admin_handlers.py` —
  conventions match the existing thin-handler pattern)
- ~6 repo methods added (`find_tombstoned_by_org`,
  `*_with_deleted` variants)
- ~15 backend pytest cases (happy path, role gating, partial-failure
  restore, cascade-aware parent flagging, time-window edges)

**Frontend**:
- 1 new page + 1 new client component (~250 LoC)
- 2 new API proxy routes (~30 LoC each)
- 1 sidebar entry (visibility gated by role)
- ~12 vitest tests (renders, filters, bulk select, restore success +
  failure, role-gated visibility)

**Tests**:
- Backend pytest: ~15 new + 0 modified. Coverage stays ≥ 95%.
- Frontend vitest: ~12 new + 0 modified.
- E2E: 1 new flow — admin user deletes an analysis, navigates to
  Recently Deleted, restores it, verifies it reappears.

**Operational**:
- No infra changes (no new tables, no new IAM grants beyond what
  the existing API Lambda already has).
- Activity feed projection is cross-referenced — see the
  follow-up change `activity-deleted-events` for emission of
  `*_deleted` and `*_restored` events. Out of scope here.

**Migration / risk**:
- Zero data migration. The page surfaces existing tombstoned
  records as soon as Phase 1 is in place.

## What We're NOT Doing

- **Permanent delete from the UI** — no "Hard Delete Now" button.
  TTL handles eviction. Adding a manual hard-delete is a separate
  change with its own confirm-then-confirm UX considerations.
- **Restore preview** — no "show me what restoring this looks like"
  diff before commit. Restore is a single attribute-clear; a
  preview is overkill.
- **Cross-org impersonation** — restore is scoped to the admin's
  own org. SC0RED engineers needing cross-org recovery use direct
  DynamoDB tooling (the engineer-assisted path from Phase 1).
- **Audit log of who restored what** — basic auditability via
  CloudWatch logs from the handler. A persistent audit table is a
  separate compliance discussion.
- **Restoring records older than 90 days** — TTL has likely already
  evicted them; if any survive (TTL eviction lag up to 48h), the UI
  surfaces them with an "Expiring soon" warning but the restore path
  works. Records that have been hard-evicted return `ttl_expired`
  in the `failed` payload.
- **Phase-3 hard-delete cron** — TTL covers it. If we later need
  precise eviction (GDPR right-to-be-forgotten), that's a separate
  change.

## Open Questions (resolve at apply time)

1. **Should the time-window default be 30d or 7d?** — 30d covers the
   "noticed a week later" case better; 7d is a smaller default
   payload. Decision: 30d default, escalate to 90d via the chip.

2. **Should restore preserve the original `deleted_at` as a
   `last_deleted_at` or wipe it entirely?** — Wipe entirely. The
   record is back to "live" state; tracking historical
   delete-then-restore cycles isn't worth the schema bloat. Audit
   log via CloudWatch covers it.

3. **Should restore emit a frontend Toast that says "Don't forget to
   tell the team this was restored"?** — Probably overkill. Stick
   with the standard "Restored N records" success toast. Activity
   feed changes (separate proposal) will surface restores naturally.

4. **What if an admin tries to restore an analysis whose parent
   scan was hard-evicted (>90d gone, TTL caught it)?** — The
   analysis can still be restored; it lives "unparented" (no scan
   to display "Part of:" for). Phase 1 design D5 already documents
   this edge. UI surfaces a warning: "Parent scan no longer exists.
   This analysis will be restored without a scan link."
