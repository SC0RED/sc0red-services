# Tasks — Recently Deleted (Phase 2 of Soft-Delete with Recovery)

> **Prerequisite:** `soft-delete-recovery` must be applied (or applied
> in the same atomic deploy) before this change can ship. Without
> tombstones, this UI has nothing to display.

## 1. Backend — repository methods

- [ ] 1.1 `DynamoDBCompanyRepository.find_tombstoned_by_org(org_id,
      window_start: datetime)` — returns companies for the org with
      `deleted_at >= window_start`. Internally: GSI1 query +
      in-memory filter on `deleted_at` (revisit GSI on `deleted_at`
      if perf becomes an issue).
- [ ] 1.2 `DynamoDBScanRepository.find_tombstoned_by_org(...)` —
      same shape.
- [ ] 1.3 `DynamoDBCompanyRepository.get_by_id_with_deleted(id)` —
      bypasses the live-only filter; used by the restore handler
      to look up tombstoned records.
- [ ] 1.4 `DynamoDBScanRepository.get_by_id_with_deleted(id)` —
      same.
- [ ] 1.5 Existing `restore(id)` from Phase 1 stays as-is.
- [ ] 1.6 Unit tests for each of the above.

## 2. Backend — handler module

- [ ] 2.1 New `backend/src/handlers/admin_handlers.py` with
      `handle_get_recently_deleted` and `handle_admin_restore`.
- [ ] 2.2 `handle_get_recently_deleted`:
      - Parse `?window=` query param; default 30d, max 90d.
      - Validate `authentication.role == "admin"`; 403 otherwise.
      - Fetch tombstoned scans + tombstoned companies for the org.
      - Resolve actor names via `user_repo.find_by_org` (one call,
        build id→name map).
      - For each analysis, check whether its parent scan is
        tombstoned (set `parentTombstoned: true` if so).
      - Sort by `deleted_at` descending; return.
- [ ] 2.3 `handle_admin_restore`:
      - Validate body shape (`{ids: string[]}` non-empty).
      - Validate `authentication.role == "admin"`; 403 otherwise.
      - For each id: try `company_repo.get_by_id_with_deleted` first,
        then `scan_repo.get_by_id_with_deleted` if not a company.
      - Org-mismatch + not-found both surface as `not_found` in
        the `failed` array.
      - TTL-expired (record was hard-evicted between list and
        restore) surfaces as `ttl_expired`.
      - Restore via `*_repo.restore(id)`.
- [ ] 2.4 Register both routes in `api_gateway_handler.py` under
      `/api/admin/recently-deleted` and `/api/admin/restore`.

## 3. Backend tests

- [ ] 3.1 `test_admin_recently_deleted_lists_org_tombstones`
- [ ] 3.2 `test_admin_recently_deleted_respects_window`
- [ ] 3.3 `test_admin_recently_deleted_resolves_actor_names`
- [ ] 3.4 `test_admin_recently_deleted_flags_parent_tombstoned`
- [ ] 3.5 `test_admin_recently_deleted_returns_403_for_analyst_role`
- [ ] 3.6 `test_admin_recently_deleted_default_window_30d`
- [ ] 3.7 `test_admin_recently_deleted_clamps_window_to_90d`
- [ ] 3.8 `test_admin_restore_clears_tombstone`
- [ ] 3.9 `test_admin_restore_handles_mixed_record_types`
- [ ] 3.10 `test_admin_restore_partial_failure_returns_failed_array`
- [ ] 3.11 `test_admin_restore_returns_403_for_analyst_role`
- [ ] 3.12 `test_admin_restore_org_isolation` (cross-org id surfaces
       as `not_found`)
- [ ] 3.13 `test_admin_restore_idempotent` (restoring a non-
       tombstoned record is a no-op, not an error)

## 4. Frontend — types

- [ ] 4.1 Add `RecentlyDeletedRecord` and
      `RecentlyDeletedResponse` types to
      `frontend/src/lib/types/api.ts`.
- [ ] 4.2 Add `RestoreResponse` type for the POST result.
- [ ] 4.3 Add an `AdminRole` literal type if it doesn't already
      exist.

## 5. Frontend — API proxy routes

- [ ] 5.1 `frontend/src/app/api/admin/recently-deleted/route.ts` —
      GET only, forwards via `backendFetch`.
- [ ] 5.2 `frontend/src/app/api/admin/restore/route.ts` — POST only,
      forwards via `backendFetch`.
- [ ] 5.3 Both: 5 vitest tests each (happy path, 401, 403, 400,
      500) following the established proxy-route pattern from §2
      analytics + §5 activity.

## 6. Frontend — page + component

- [ ] 6.1 `frontend/src/app/(authenticated)/settings/recently-
      deleted/page.tsx` — server component. Reads session, returns
      404 (not 403) for non-admins so the page doesn't advertise
      its existence. Fetches the initial list and passes to client.
- [ ] 6.2 `frontend/src/components/RecentlyDeletedView.tsx` —
      client component. Owns the time-window chip state, search
      input, table rendering, selection state, restore action.
- [ ] 6.3 Reuse `BulkActionsBar` for the bulk-restore action.
      Extension: add optional `onRestore` prop + `restoreLabel`.
      Update existing component signature; existing consumers
      (analyses list) keep working unchanged.
- [ ] 6.4 Reuse `RelativeTime` for the deleted-at column.
- [ ] 6.5 Empty state: friendly copy + link to `/analyses` so
      admins understand where they came from.

## 7. Frontend — sidebar entry

- [ ] 7.1 Add a "Recently Deleted" entry to
      `frontend/src/components/sidebar/navItems.tsx` under Settings.
      Mark `adminOnly: true` so the existing sidebar render filter
      hides it for analysts.

## 8. Frontend tests

- [ ] 8.1 `RecentlyDeletedView.test.tsx`:
      - Renders empty state when records list is empty
      - Renders rows with displayName, type, actor, RelativeTime
      - Filter chip (24h/7d/30d/90d) updates the API request
      - Search filters rows client-side
      - Selection toggles BulkActionsBar with "Restore N" label
      - Per-row Restore fires POST with single id
      - Bulk Restore fires POST with array of ids
      - Parent-tombstoned pill renders when flag is set
      - Restore success: row disappears + Toast success
      - Restore partial failure: row stays + Toast error with count
- [ ] 8.2 Sidebar test: "Recently Deleted" entry only renders for
      admin role.

## 9. E2E flow

- [ ] 9.1 Add a Playwright flow:
      - Log in as admin
      - Run a scan, get analyses
      - Bulk-delete some analyses
      - Navigate to Settings → Recently Deleted
      - Filter to 24h, see the deleted records
      - Click Restore on one
      - Navigate to /analyses, verify the row reappeared

## 10. Quality gates

- [ ] 10.1 `cd backend && uv run ruff check src/` clean
- [ ] 10.2 `cd backend && uv run pyright src/` no new errors
- [ ] 10.3 `cd backend && uv run pytest tests/ -q` all green;
      coverage ≥ 95%
- [ ] 10.4 `cd frontend && npm run lint && npx tsc --noEmit && npm test`
      all clean
- [ ] 10.5 Architecture-reviewer agent run on the combined diff
- [ ] 10.6 E2E (`E2E_MODE=full`) including the new flow

## 11. Rollout

- [ ] 11.1 Deploy to development. Manual verification flow
      (delete-then-restore as admin).
- [ ] 11.2 Deploy to testing.
- [ ] 11.3 Deploy to production.
- [ ] 11.4 Update `docs/runbooks/`: replace the engineer-assisted
      recovery runbook from Phase 1 with a "Use the Recently
      Deleted UI; engineer recovery is the escape hatch" note.

## 12. Closeout

- [ ] 12.1 Update Phase 1 (`soft-delete-recovery`) archived spec to
      reference Phase 2's existence.
- [ ] 12.2 Open follow-up: `activity-deleted-events` — once Phase
      2 is stable, project `*_deleted` and `*_restored` events to
      the activity feed. Tier 2 §5 cross-reference: the existing
      activity-feed handler currently documents "deletes are
      unprojectable"; tombstones invalidate that limitation.
- [ ] 12.3 Archive this change via `/opsx:archive` once production
      is stable for 1 week.
