## Why

Across multiple admin and activity surfaces, action attribution falls back to a placeholder string (or, worse, a raw UUID) instead of the actor's name. PR #215 (`recently-deleted-admin-ui`) made this visible: deleting a record post-deploy, then opening `/settings/recently-deleted`, renders the `DELETED BY` cell as a UUID — `719cfd78-2eab-4288-bb93-923813d1e650` rather than `ved`. The same root cause has been silently hiding in the dashboard activity feed for longer: items render as "Someone started a portfolio scan" and "An admin invited …" because the actor lookup fails.

Root cause: every actor field stored on records (`deleted_by`, `created_by`, `invited_by`) is sourced from `authentication.user_id`, which `auth_middleware.extract_auth_context` populates from the JWT in this priority:

```python
user_id = payload.get("custom:legacy_user_id") or payload.get("sub") or payload.get("id", "")
```

In dev (verified via `GET /api/org/members` returning `{ "members": [], "pendingInvitations": [] }` while logged in as an admin), the JWT carries only `sub` — the Cognito user-pool UUID — not the `custom:legacy_user_id` attribute that maps to the internal `user["id"]`. So `authentication.user_id` becomes the Cognito sub. When admin handlers and activity handlers later do `user_repo.find_by_org(org_id)` to build a `{user["id"]: user}` lookup map and resolve actor names, the lookup misses every time because the actor ids stored on records don't match any `user["id"]` in the org.

The bug spans three call sites with two failure modes:

| Surface | Code | Fallback |
|---|---|---|
| Recently Deleted (PR #215) | `admin_handlers._resolve_actor` line 192 | `{"id": actor_id, "name": actor_id}` — leaks UUID into UI |
| Activity feed (`scan_started`, `analysis_completed`) | `activity_handlers` lines 161, 195 | `"Someone"` / `"An analyst"` |
| Activity feed (`member_invited`) | `activity_handlers` line 216 | `"An admin"` |

The Recently Deleted surface is the loudest because it renders the actor id as the actor name when the lookup fails — a privacy/UX leak that PR #215 inherits from the wider attribution bug, not introduces. The activity feed surfaces hide the failure behind friendly placeholders, but they're symptomatic of the same broken contract.

Fixing this at one of the three call sites (the original `fix-deleted-by-display` proposal) only patches the symptom on one surface. Fixing it once, at the boundary, repairs all three.

## What Changes

- **`auth_middleware.extract_auth_context`** — when the JWT carries no `custom:legacy_user_id`, resolve `authentication.user_id` to the internal `user["id"]` by looking up the user record by `cognito_sub` (preferred) or `email` (fallback). Cache the lookup on the request so the cost is one read per authenticated call, not one per handler. After this change, `authentication.user_id` is always the internal id — handlers no longer need to know there's a translation step.
- **`user_repository.DynamoDBUserRepository`** — add `find_by_cognito_sub(sub: str) -> dict | None` plus update `create()` to populate `GSI5PK = "COGNITO_SUB#{sub}"` on every NEW user record. Records written via the existing register flow already store `cognito_sub` as a plain attribute (set in `auth_handlers.handle_register` from the Cognito `admin_create_user` response). However, **no GSI is keyed on `cognito_sub`** today — the table has 4 GSIs (`GSI1`-`GSI4` per `scripts/setup_dynamodb.py:8` and `infrastructure/stacks/stack_resources.py:31`), none indexed on this field. Adding a 5th GSI is therefore part of this change. The change ships in **1 PR** because the middleware fallback chain (`legacy_user_id → cognito_sub → email`) degrades gracefully — `find_by_email` uses GSI4 (which exists and is populated for every user record today), so authenticated requests keep working during the GSI5 `CREATING` window and for any record that hasn't been backfilled yet. Operational sequencing is post-deploy, not pre-deploy.
- **Capture `created_by` on company creation** — `activity_handlers.py:193` reads `company.get("created_by", "")` for `analysis_completed` events, but no code path writes it onto company records today. Add `"created_by": authentication.user_id` to every handler that creates a company record so the activity feed has an actor to resolve. One-line change per call site; mirrors the `deleted_by` capture from PR #215.
- **Backfill data on dev + test + production** — for every existing tombstone (`deleted_by`) and historical `created_by` / `invited_by` value that is currently a Cognito sub, translate to the internal user id. One-shot script under `scripts/backfill_actor_ids.py` with idempotent dry-run mode. Backfill is required because the Recently Deleted UI reads `deleted_by` directly — without backfill, old tombstones continue to render as UUIDs even after the write-time fix.
- **Remove the actor-id leak fallback** in `admin_handlers._resolve_actor` — change line 192 from `return {"id": actor_id, "name": actor_id}` to `return {"id": actor_id, "name": "Unknown"}`. With the auth-middleware fix in place, this path should be reached only for genuinely off-boarded users; surfacing "Unknown" is correct, surfacing the raw id was a UI leak.

After these four changes, the Recently Deleted UI shows `Deleted by ved`, the dashboard activity feed shows `ved started a portfolio scan` / `ved invited vedpatel2006@gmail.com`, and any future surface that wants to attribute an action just reads the stored id and resolves through the same per-org user map.

## Capabilities

### New Capabilities
_(None — bug fix.)_

### Modified Capabilities
_(None — internal correction. The user-visible behaviour change is "names render correctly" — no new contract surfaces.)_

## Impact

**Modified**:
- `backend/src/handlers/auth_middleware.py` — boundary fix for `user_id` resolution
- `backend/src/repositories/dynamodb/user_repository.py` — new `find_by_cognito_sub`
- `backend/src/handlers/admin_handlers.py` — `_resolve_actor` fallback ("Unknown" instead of raw id)
- `backend/tests/unit/handlers/test_auth_middleware.py` — new cases for sub/email fallback paths
- `backend/tests/unit/handlers/test_admin_handlers.py` — update `_resolve_actor` fallback assertion
- `backend/tests/unit/repositories/test_user_repository.py` — new `find_by_cognito_sub` cases

**Added**:
- `backend/scripts/backfill_actor_ids.py` — one-shot, idempotent, dry-run by default

**Tests**:
- ~6 new pytest cases (auth middleware fallback paths, user repo lookup, fallback rendering)
- ~2 modified cases (existing `_resolve_actor` test asserts UUID fallback — flips to `"Unknown"`)
- Coverage stays ≥ 95%

**Operational**:
- Backfill runs once per environment after deploy. Idempotent — re-running translates only the records still pointing at Cognito subs. Dry-run output documented in `tasks.md` §5.
- Per-request cost: one extra `user_repo.find_by_cognito_sub` lookup per authenticated request when `custom:legacy_user_id` is absent. Negligible (single-item GSI query) and bounded — long-term solution is to fix the JWT issuance path so `custom:legacy_user_id` is always present.

**Migration / risk**:
- Backfill is a one-shot script with a dry-run flag; reviewer signs off on the dry-run diff before the live run.
- Auth-middleware change is additive — falls through to existing behaviour when the lookup fails. No risk of locking out users.
- The `_resolve_actor` fallback flip is purely UI; no data implications.

## What We're NOT Doing

- **Fixing JWT issuance to always include `custom:legacy_user_id`** — that's a Cognito User Pool configuration change (token customisation Lambda or custom claims). Worth doing but separate scope; this proposal makes the backend resilient even if the JWT only carries `sub`, which is the more defensive fix.
- **Migrating to `cognito_sub` as the primary user id** — would erase the `id` ↔ `cognito_sub` distinction entirely. Bigger blast radius (every foreign-key reference to `user["id"]` would need rewriting); rejected as scope.
- **Persistent audit log of who-did-what** — out of scope. CloudWatch logs cover engineer-side audit; user-visible attribution is what this fix corrects.
- **Backfilling activity-feed events that are already projected** — the activity feed reads actor ids fresh from the source records on each `/api/activity` call (no projection table yet). Once the source records are backfilled, the feed renders correctly without separate intervention.

## Open Questions (resolve at apply time)

1. **Backfill scope on production** — how many records currently have a Cognito sub in `deleted_by` / `created_by` / `invited_by`? Dry-run output answers this. If the count is in the thousands, run during a quiet window; if in the millions, batch with throttling.

2. **What about records where the Cognito sub doesn't resolve to any current user (off-boarded user)?** — backfill leaves those untouched. The runtime `_resolve_actor` already handles this case correctly (falls through to "Unknown" once the leak fix lands). Document the expected count in the dry-run.

3. **Should `extract_auth_context` cache the resolved id on the JWT itself?** — no. The lookup happens once per request (the AuthContext is built once and threaded through), so no in-process caching is needed. Cross-request caching would invalidate poorly when users get off-boarded.
