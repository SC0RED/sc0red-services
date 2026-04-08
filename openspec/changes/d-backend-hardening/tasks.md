# Tasks: Backend Hardening

## Structured error responses

- [x] Update `build_error()` to accept an error code parameter and include it in the response body
- [x] Define error code constants (VALIDATION_ERROR, NOT_FOUND, UNAUTHORIZED, FORBIDDEN, CONFLICT, etc.)
- [x] Update all `build_error()` calls across handlers to pass the appropriate error code
- [x] Update existing tests to verify error codes in responses

## Org authorization helper

- [x] Create `check_org_access()` helper that returns 404 error if resource is missing or belongs to different org
- [x] Replace 10 manual org_id checks across handlers with check_org_access()

## Request correlation IDs

- [x] Generate or extract correlation ID in the main handler dispatch
- [x] Add correlation ID to all log entries for the request
- [x] Include correlation ID in response headers (`X-Request-Id`)
- [x] Include correlation ID in error responses (via _finalize on all paths)
