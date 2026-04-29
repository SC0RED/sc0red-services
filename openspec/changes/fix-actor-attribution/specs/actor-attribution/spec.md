## ADDED Requirements

### Requirement: AuthContext.user_id is always the internal user id

`auth_middleware.extract_auth_context` SHALL populate `AuthContext.user_id` with the internal `user["id"]` from the user record, regardless of whether the JWT carries the `custom:legacy_user_id` claim. Resolution priority is: `custom:legacy_user_id` from the token → `user_repository.find_by_cognito_sub(token.sub)` → `user_repository.find_by_email(token.email)`. If all three fail, `extract_auth_context` SHALL raise `ValueError` with the same "Token missing user identifier" semantics that exist today.

After this change, downstream handlers MUST NOT need to translate `authentication.user_id` to an internal id — the translation has already happened at the boundary.

#### Scenario: JWT carries `custom:legacy_user_id`

- **WHEN** the token contains `custom:legacy_user_id`
- **THEN** `AuthContext.user_id` is set from that claim directly
- **AND** no DynamoDB lookup happens

#### Scenario: JWT lacks `custom:legacy_user_id` but a user record matches the Cognito sub

- **WHEN** the token has only `sub` (no `custom:legacy_user_id`)
- **AND** a user record exists with `cognito_sub` matching the token's `sub`
- **THEN** `AuthContext.user_id` is set to that user record's `id`

#### Scenario: JWT lacks `custom:legacy_user_id` and no record carries the Cognito sub but email matches

- **WHEN** the token has only `sub` and `email`
- **AND** no user record has `cognito_sub` matching `sub` (e.g., legacy record predating sub-tracking)
- **AND** a user record exists with the matching email
- **THEN** `AuthContext.user_id` is set to that user record's `id`

#### Scenario: All three lookups fail

- **WHEN** the token has no `custom:legacy_user_id`, no record carries the sub, and no record matches the email
- **THEN** `extract_auth_context` raises `ValueError`
- **AND** the request is rejected with 401

### Requirement: User records are queryable by Cognito sub

`DynamoDBUserRepository` SHALL expose a `find_by_cognito_sub(sub: str) -> dict | None` method that returns the user record whose `cognito_sub` attribute matches the supplied value, or `None` if no record matches. The lookup SHALL be a single-item GSI query, not a Scan.

This requires a Global Secondary Index keyed on `cognito_sub`. The index MUST be deployed and reach `ACTIVE` status before any consumer of `find_by_cognito_sub` ships, otherwise the lookup either returns `None` for every existing record (sparse-index reality on day 0) or fails with `ValidationException`.

#### Scenario: Lookup returns the matching user

- **WHEN** a user record exists with `cognito_sub = "abc-123"`
- **AND** `find_by_cognito_sub("abc-123")` is called
- **THEN** that user record is returned

#### Scenario: Lookup returns None for unknown sub

- **WHEN** no user record has `cognito_sub = "ghost-id"`
- **AND** `find_by_cognito_sub("ghost-id")` is called
- **THEN** `None` is returned

### Requirement: Stored actor ids on records are internal user ids, never Cognito subs

Every record that stores an actor reference (`deleted_by`, `created_by`, `invited_by`) SHALL store the internal `user["id"]`, not the Cognito sub. Since `AuthContext.user_id` is now always the internal id (per the auth-boundary requirement above), call sites can continue using `authentication.user_id` directly with no per-call-site translation.

This requirement is automatically satisfied for every NEW write after the auth-boundary fix lands. EXISTING records that were written before the fix and currently carry Cognito subs in these fields SHALL be translated by a one-shot backfill script that:
- Pre-builds `set(user_ids)` and `dict(cognito_sub -> user_id)` once at script start.
- Translates every value that matches a Cognito sub to the corresponding `user_id`.
- Is idempotent: values already matching a known `user_id` are left untouched.
- Logs unresolved values (subs that match no current user — typically off-boarded users) without modifying them.
- Saves a JSON diff log per `--apply` run for selective rollback.

#### Scenario: Backfill translates a Cognito sub on a tombstoned company

- **WHEN** a company record has `deleted_by = "<some-cognito-sub>"`
- **AND** that sub corresponds to user record `user_id = "u-1"`
- **AND** the backfill script runs in `--apply` mode
- **THEN** the company record's `deleted_by` is updated to `"u-1"`

#### Scenario: Backfill is idempotent on already-translated records

- **WHEN** a record's actor field already contains a known `user_id`
- **AND** the backfill script runs (in either `--dry-run` or `--apply` mode)
- **THEN** the record is left untouched

#### Scenario: Backfill leaves off-boarded-user references unchanged

- **WHEN** a record's actor field contains a Cognito sub that matches no current user
- **AND** the backfill script runs
- **THEN** the record is left untouched and the unresolved sub is logged

### Requirement: Activity feed and admin UI render actor names, not raw ids

When a stored actor id resolves to a user record in the org, the rendered name in the activity feed and Recently Deleted admin UI SHALL be the user's display name (`user["name"]`), falling back to `user["email"]` if name is empty, falling back to the literal string `"Unknown"` if no record resolves.

The fallback string MUST NOT be the raw actor id (no UUID leak in user-facing surfaces). The fallback string MUST NOT vary across the activity feed event types and the Recently Deleted UI — `"Unknown"` everywhere; "Someone" / "An admin" / "An analyst" placeholders SHOULD only fire for records with NO actor id stored at all (legacy records predating the actor-capture write paths).

#### Scenario: Recently Deleted UI renders the resolved actor name

- **WHEN** a tombstoned record has `deleted_by = "u-1"`
- **AND** user record `u-1` exists in the org with `name = "Alice"`
- **THEN** the UI's "Deleted by" cell renders `"Alice"`

#### Scenario: Recently Deleted UI renders "Unknown" for off-boarded actors

- **WHEN** a tombstoned record has `deleted_by = "u-9"`
- **AND** no user record `u-9` exists in the current org
- **THEN** the UI's "Deleted by" cell renders `"Unknown"`
- **AND** the cell does NOT render the raw `u-9` id

### Requirement: New analysis records capture `created_by`

Handlers that create company records SHALL persist `created_by = authentication.user_id` on the new record, so the activity feed's `analysis_completed` event can attribute the action to the correct user.

This closes a gap where `activity_handlers.py` reads `company.get("created_by", "")` for the `analysis_completed` event but no code path was writing the field. Existing records without `created_by` continue to render the "An analyst" placeholder by structural absence — backfill is not required for this field because no recoverable actor identity exists for them.

#### Scenario: New analysis surfaces the creator in the activity feed

- **WHEN** user `Alice` triggers a scan that produces analyses
- **AND** the activity feed projects `analysis_completed` events from those analyses
- **THEN** each event renders `"Alice analyzed <company>"`, not `"An analyst analyzed <company>"`
