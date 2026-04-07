# Package D: Backend Hardening

**Impact**: Medium | **Effort**: Low | **Priority**: After Package 0

## Problem

Backend has scattered patterns that make debugging harder, error responses inconsistent, and authorization checks duplicated across handlers.

## Proposal

Quick, low-risk improvements to the backend API contract. These changes make every subsequent package easier because they improve the foundation.

## Changes

### 1. Org authorization middleware

Currently, every handler that loads a resource manually checks `if resource.get("org_id") != authentication.org_id`. This pattern is repeated 6+ times. Extract into a decorator or middleware that returns 403 automatically.

### 2. Structured error responses

Add error codes to API responses. Current: `{"error": "Not found"}`. Proposed: `{"error": "Not found", "code": "RESOURCE_NOT_FOUND"}`. This lets the frontend handle errors programmatically instead of pattern-matching strings.

### 3. Request correlation IDs

Generate a correlation ID per request (or use X-Ray trace ID) and include it in:
- All log entries for that request
- The response headers (`X-Request-Id`)
- Error responses (so users can report issues with a reference)

### 4. Consistent error messages

Audit all `build_error()` calls and standardize the format. Define error codes for common cases: `VALIDATION_ERROR`, `NOT_FOUND`, `UNAUTHORIZED`, `FORBIDDEN`, `CONFLICT`.

### 5. API response time logging

Add timing to the main handler dispatch — log method, path, status code, and duration for every request. Enables CloudWatch Insights queries for latency analysis.

## What we DON'T change

- No handler refactoring (that's Package E)
- No DynamoDB changes (that's Package C)
- No new endpoints
- No breaking API changes (error codes are additive)

## Success criteria

- [ ] Org isolation enforced via decorator, not manual checks
- [ ] All error responses include `code` field
- [ ] Request correlation ID in logs and response headers
- [ ] Every API request logs method + path + status + duration
- [ ] Zero test regressions (all 557 existing tests pass)
