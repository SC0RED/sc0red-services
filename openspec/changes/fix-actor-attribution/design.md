## Context

The bug spans three handlers (`admin_handlers._resolve_actor`, `activity_handlers.actor_names`, and any future surface that wants to attribute a stored action), but the root cause is a single mismatch at the auth boundary: `authentication.user_id` carries the Cognito sub when the JWT lacks `custom:legacy_user_id`, while every user record in DynamoDB is keyed by an unrelated internal UUID. Each handler then does its own version of `user_repo.find_by_org` + dict lookup, fails identically, and falls through to its own placeholder string.

Two surfaces make the failure user-visible:

```
Recently Deleted (PR #215):     Deleted by 719cfd78-2eab-4288-bb93-923813d1e650
Activity feed:                  Someone started a portfolio scan
Activity feed (invitation):     An admin invited vedpatel2006@gmail.com
```

The fix has to land at the boundary. Patching `_resolve_actor` alone leaves the activity feed broken; patching both leaves the next surface to discover the same bug. The right move is to make `authentication.user_id` always be the internal `user["id"]`, so handlers stop needing to know there's a translation step.

## Goals / Non-Goals

**Goals:**
- After this change, `authentication.user_id` is always the internal `user["id"]` regardless of whether the JWT carries `custom:legacy_user_id`.
- Existing records with Cognito subs in `deleted_by` / `created_by` / `invited_by` are translated by a one-shot backfill so historical attribution renders correctly without re-deletion or re-creation.
- The `_resolve_actor` UI leak (rendering UUID as name) is closed.
- The activity feed stops using "Someone" / "An admin" placeholders for actors who actually exist in the org.

**Non-Goals:**
- Reconfiguring Cognito to always include `custom:legacy_user_id` in JWTs. Worth doing later; this fix is the defensive layer that works even if Cognito tokens stay as-is.
- Schema migration to use `cognito_sub` as the primary user id. Too big a blast radius.
- A persistent audit log of who-did-what. CloudWatch covers engineer-side audit.

## Decisions

### D1. Translate at the auth boundary, not at every read site

**Decision:** `auth_middleware.extract_auth_context` resolves `authentication.user_id` to the internal user id. If the JWT carries `custom:legacy_user_id`, use it directly (matches today's behaviour). If not, look up the user by `cognito_sub` (preferred) or `email` (fallback) and use the returned `user["id"]`. If neither lookup resolves, raise `ValueError` exactly as the existing "Token missing user identifier" path does — better to fail loudly than to surface a stranger's id downstream.

**Why the boundary, not the call sites:** there are three known read sites today (`admin_handlers._resolve_actor`, `activity_handlers.actor_names` × 3 event types). Patching each one duplicates logic, leaks the abstraction, and means the next surface that wants attribution will discover the bug all over again. CLAUDE.md's "search the codebase for how similar work is already done" guidance pushes the same way: one resolution path, not three.

**Why prefer `cognito_sub` over `email`:** email is mutable (users change addresses); Cognito sub is the issued JWT subject and is stable. The user record carries both today (set at register time in `auth_handlers.handle_register`).

**Why fall through to email lookup:** historical user records may not have `cognito_sub` populated (the field was added later). Email lookup provides the migration path without forcing a separate user-record backfill.

### D2. Backfill historical actor ids in stored records

**Decision:** ship a one-shot script (`scripts/backfill_actor_ids.py`) that scans every record carrying a `deleted_by` / `created_by` / `invited_by` field, attempts to translate any value that matches an existing Cognito sub into the internal user id, and writes the corrected value back. Default mode is `--dry-run`; the live mode requires `--apply`.

**Why backfill is required:** the Recently Deleted UI and the activity feed read these fields directly from source records. Without backfill, the auth-middleware fix corrects only future writes — old tombstones continue to render as UUIDs even though new ones render correctly. That's worse than the current state because users will see inconsistent behaviour ("yesterday's deletion shows my name; last week's shows a UUID").

**Why one-shot, not migration-on-read:** translation-on-read would leak the Cognito-id concern back into every read site, defeating D1. Once data is backfilled, all read sites stay simple.

**Why idempotent:** so it can re-run safely. Translating an already-translated id is a no-op (the value already matches a `user["id"]`, not a Cognito sub).

### D3. Rendering fallback is "Unknown", not the raw id

**Decision:** when an actor id resolves to no user record, `_resolve_actor` returns `{"id": actor_id, "name": "Unknown"}` instead of `{"id": actor_id, "name": actor_id}`.

**Why:** with D1 + D2 in place, the only remaining failure path is "the user existed when the action was taken but has since been off-boarded from the org." Surfacing the raw id was always wrong — it leaks an internal UUID that has no value to a human reader and makes screenshots look broken. "Unknown" matches what the frontend already renders when `deletedBy` is null (legacy tombstones with no `deleted_by` written at all), so the user-facing semantic is consistent: "we cannot attribute this action to a current user."

**Why keep the `id` field in the response:** retained for parity with the activity feed's `actor: {id, name}` shape and to leave the door open for "click to view user profile" affordances later. Even when resolving fails, the id is what we have.

### D4. Cost: one user-lookup per authenticated request when fallback fires

**Decision:** accept the per-request cost of `user_repo.find_by_cognito_sub` (or `find_by_email`) when the JWT lacks `custom:legacy_user_id`. No caching across requests.

**Why no cache:** the AuthContext lifecycle is per-request; there's nothing to cache across. Cross-request caching (e.g. Redis) would need invalidation on user off-boarding/deletion, and the lookup is a single-item GSI query — sub-millisecond. Premature optimisation.

**Long-term:** the better fix is the Cognito-side change (always include `custom:legacy_user_id` in tokens). That's tracked as a follow-up but explicitly out of scope here, because we want the backend to be resilient regardless of token shape — the token is an external dependency we don't fully control.

## Risks

| Risk | Mitigation |
|---|---|
| GSI on `cognito_sub` doesn't exist (confirmed: no GSI today) | This change adds GSI5 in CDK + updates `user_repository.create()` to write `GSI5PK = "COGNITO_SUB#{sub}"` on every new user record. Existing user records are backfilled by the `backfill_user_cognito_keys.py` script post-deploy. |
| GSI5 still `CREATING` when middleware change goes live | Acceptable. The middleware fallback chain is `legacy_user_id → cognito_sub → email`. `find_by_email` uses GSI4 (exists and populated for every user record today), so authenticated requests resolve correctly via email even while GSI5 is still being built. Once GSI5 is `ACTIVE` and the user-record backfill has populated `GSI5PK`, the cognito_sub path becomes the primary resolution. |
| Backfill misattributes a record (translates to the wrong user) | Translation is keyed on Cognito sub, which is stable and unique per user. Misattribution would require two users to share a sub, which Cognito guarantees against. Email-fallback path is a slim risk if two records share an email — guarded by surfacing collisions in dry-run output. |
| Auth-middleware lookup adds latency | Single-item GSI query, < 5 ms p99 in our existing telemetry. Goes to zero once Cognito starts emitting `custom:legacy_user_id` (separate follow-up). |
| Records pointing at off-boarded users | `_resolve_actor` returns `"Unknown"` correctly; same UX as the existing "no `deleted_by` written" path. |

## Open Questions

1. **Production backfill volume** — answered by `--dry-run` output of the backfill script before the live run.
