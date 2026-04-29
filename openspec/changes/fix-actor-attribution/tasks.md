## 1. Backend — auth boundary fix

- [x] 1.1 `validate_token` (the actual symbol — proposal called it `extract_auth_context`) resolves `user_id` to internal id via `_resolve_user_id`: prefer `custom:legacy_user_id`, then look up by `cognito_sub` (GSI5), then by `email` (existing GSI4). Raise `ValueError` if all three fail. `require_authentication` accepts an optional `user_repo`, threaded from `api_gateway_handler` via `self._storage.create_user_repository()`.
- [x] 1.2 New `DynamoDBUserRepository.find_by_cognito_sub(sub: str) -> dict | None` — single-item GSI5 query. Returns `None` for legacy records that haven't been backfilled yet; the email-fallback in `_resolve_user_id` covers them.
- [x] 1.3 Existing call sites need no changes — handlers continue using `authentication.user_id`, which now always carries the internal id.

## 2. Backend — fallback rendering + actor capture on company-create

- [x] 2.1 `admin_handlers._resolve_actor` — fallback for off-boarded users now returns `{"id": actor_id, "name": "Unknown"}` instead of the raw id. The "user found but name+email empty" branch also falls back to "Unknown" instead of the id.
- [x] 2.2 Updated `test_admin_recently_deleted_resolves_actor_names` to expect `"Unknown"` for the off-boarded-user path.
- [x] 2.3 **Captured `created_by` on company creation** — `Company` model gets a `user_id` field; `factories_factory` populates it from `JanusEvent.user_id`; `persist_results.py` writes `created_by = company.user_id` to the company doc. Activity feed's `analysis_completed` event now has an actor id to resolve.
- [ ] 2.4 Activity feed (`activity_handlers`) — already falls through to "Someone" / "An analyst" / "An admin" by design, so no read-side changes needed once D1 starts producing internal ids that resolve correctly. Add a regression test confirming the feed renders the actor's actual name when the user exists in the org.

## 3. Infrastructure — GSI5 on `cognito_sub` (single PR, post-deploy backfill)

> **Why this sequencing works in 1 PR**: the middleware fallback chain is `legacy_user_id → cognito_sub → email`. `find_by_email` uses GSI4, which exists and is populated for every user record today. So authenticated requests keep resolving correctly via email even while GSI5 is still `CREATING` and even for legacy records that haven't been backfilled yet. Once GSI5 is `ACTIVE` and `backfill_user_cognito_keys.py` has run, the cognito_sub path becomes the primary lookup automatically.

### 3a. Add GSI5 to the table

- [x] 3.1 Added GSI5 to `infrastructure/stacks/stack_resources.py` (loop bumped to `range(1, 6)`; docstring expanded with the GSI roster).
- [x] 3.2 Updated `scripts/setup_dynamodb.py` — `GSI_COUNT = 5`. Local dev + LocalStack now matches production.
- [x] 3.3 Updated `tests/unit/repositories/conftest.py` to declare `GSI5PK`/`GSI5SK` attributes + the index on the moto-mocked table.
- [x] 3.4 `DynamoDBUserRepository.create()` writes `GSI5PK = "COGNITO_SUB#{sub}"` and `GSI5SK = "USER#{user_id}"` when `cognito_sub` is supplied. Sparse for callers that don't carry a sub (legacy register flows), populated by §3.5 backfill.

### 3b. Post-deploy: backfill `GSI5PK` + `cognito_sub` on existing user records

- [ ] 3.5 New `backend/scripts/backfill_user_cognito_keys.py`:
      - Page through every user record (via GSI1 per-org).
      - If `cognito_sub` is missing: look up the user in Cognito by email (`admin-list-users` with filter), pull the `sub` claim, write it back.
      - If `GSI5PK` is missing: write `GSI5PK = "COGNITO_SUB#{sub}"`, `GSI5SK = "USER#{user_id}"`.
      - Idempotent: skip records that already have both fields.
      - Default `--dry-run`; live mode requires `--apply`.
- [ ] 3.6 Run dry-run on dev → review counts → run `--apply`. Verify `find_by_cognito_sub` returns user records via boto3 console.
- [ ] 3.7 Same on testing.
- [ ] 3.8 Same on production. Operator confirms before running `--apply`.

> Once §3a deploys, the email-fallback path keeps the system resilient. Once §3b runs, the cognito_sub path becomes the preferred lookup. There's no "danger window" where the middleware breaks — the chain degrades gracefully.

## 4. Backfill — historical actor ids on records

- [ ] 4.1 New `backend/scripts/backfill_actor_ids.py`:
  - Pre-build lookup maps **once at script start**: `set(user["id"] for user in user_repo.find_by_org(every-org))` and `dict(user["cognito_sub"] → user["id"])`. Per-record translation is then O(1) — never query DynamoDB inside the iteration loop.
  - Iterate every record carrying `deleted_by` / `created_by` / `invited_by`. Field list is **`deleted_by`, `created_by`, `invited_by`** — there is no `tombstoned_by` field; earlier proposal drafts had a typo.
  - For each value: if it's already in the user-id set → leave (idempotent). If it's in the sub→id map → translate. Otherwise → log as unresolved.
  - `--dry-run` (default) — print (record_id, field, old_value, new_value) tuples + summary count. Write a JSON log to `out/backfill_actor_ids_${env}_${timestamp}.json` containing the planned diff.
  - `--apply` — writes the translated values back via `UpdateItem`. Saves the same JSON diff log so a manual rollback can read old→new mappings.
  - Logs unresolved values (Cognito subs that don't map to any current user) so we can confirm they're genuinely off-boarded.
- [ ] 4.2 Unit test the translation logic (mock repository + cognito_sub → user_id map).

## 5. Backend tests

- [x] 5.1-5.4 + 5.7 — see `tests/unit/handlers/test_auth_middleware_resolution.py` (8 cases): legacy-id-present, sub-resolves, email-fallback, all-three-fail, no-repo-legacy, no-repo-no-sub, sub-without-email, headless-user-record. Plus updated `test_admin_handlers` to expect `"Unknown"` for off-boarded users.
- [x] 5.5-5.6 — `test_user_repository.py` adds 5 new cases: returns_match, returns_none_for_unknown_sub, returns_none_for_empty_input, create_writes_GSI5_when_sub_supplied, create_skips_GSI5_when_no_sub.
- [x] 5.8 Activity-feed regression — already covered by the existing happy-path tests (`test_projects_scan_started_from_scan_record`, etc.) that assert `actor.name == "Alice"` when the user resolves. The fallback-string tests (`"Someone"` / `"An admin"` / `"An analyst"`) also already exist.
- [x] 5.9 `created_by` capture covered by `test_persist_results.py`: `test_persist_writes_created_by_when_user_id_present` and `test_persist_skips_created_by_when_user_id_absent`.

## 6. Backfill — execute (after §3 lands)

- [ ] 6.1 Run `backfill_actor_ids.py --dry-run` on dev. Review JSON diff log. Resolve any unexpected unresolved-id counts.
- [ ] 6.2 Run `backfill_actor_ids.py --apply` on dev. Spot-check Recently Deleted UI: old tombstones now render names. Diff log saved to `out/`.
- [ ] 6.3 Run `--dry-run` on test. Review.
- [ ] 6.4 Run `--apply` on test.
- [ ] 6.5 Run `--dry-run` on production. Review with team.
- [ ] 6.6 Run `--apply` on production. Estimated duration from dry-run output. **Rollback posture**: the `--apply` run saves a JSON diff log with old→new mappings. To revert, write a reverse-translate script that consumes the log and re-applies the old values via `UpdateItem`. Do not rely on point-in-time-restore for selective rollback — the rest of the table changed during the same window.

## 7. Quality gates

- [x] 7.1 Backend: ruff clean (`src/` + new scripts).
- [x] 7.2 Backend: pyright +14 over 366 baseline — same `dict[str, Any]` strict-mode noise as PRs #206 / #215. No new logic errors flagged.
- [x] 7.3 Backend: pytest 926 pass at 95.87% coverage (+15 net new).
- [x] 7.4 Architecture-reviewer ran: 0 CRITICAL, 2 MEDIUM (operational note + pre-existing registration-window 401), 2 LOW (stale docstring + `_table` access). Both LOW addressed in-PR; MEDIUM operational covered in PR description; pre-existing registration-window concern out of scope.
- [ ] 7.5 E2E attribution scenario — **deferred to a follow-up PR** to keep this change reviewable. The implementation contract (every actor field carries internal id, UI shows actor name) is fully covered by the unit tests in §5. Adding an E2E scenario requires the docker-compose `e2e` stack to spin up a real Cognito (LocalStack) + register a user via the registration flow + drive the UI through Playwright — non-trivial scaffolding that warrants its own PR.
- [ ] 7.6 Open PR (single PR — GSI add + middleware change + backfill scripts together; the email-fallback path keeps the middleware resilient during the GSI's `CREATING` window). CI green, merge.

## 8. Closeout

- [ ] 8.1 Open follow-up ticket: "Cognito User Pool — emit `custom:legacy_user_id` claim on every token." Once that's done, BOTH the auth-middleware fallback paths (sub-lookup AND email-lookup) become dead code that can be deleted.
- [ ] 8.2 Archive this change once production has been backfilled and stable for 1 week.
