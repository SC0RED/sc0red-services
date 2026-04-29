## 1. Frontend — extract a shared helper, then use it in both consumers

- [x] 1.1 Add `displayedCompanyCount(scan)` to `frontend/src/lib/utils/scanStatus.ts` (already has `canDeleteScan` + `IN_FLIGHT_SCAN_STATUSES`). Implementation: when `canDeleteScan(scan.status)` is true (terminal — complete or failed), return `scan.totalCompanies ?? scan.completedCount ?? 0`. Otherwise (in-flight), return `scan.completedCount ?? 0`. Use `??` (nullish-coalesce) rather than `||` so a real `0` doesn't fall through to a later non-zero value.
- [x] 1.2 `dashboard/page.tsx` line 341 — replace `{scan.completedCount || 0}` with `{displayedCompanyCount(scan)}`.
- [x] 1.3 `DeleteScanButton.tsx` consumer (called from `dashboard/page.tsx`) — replaced the inline `scan.totalCompanies || scan.completedCount` with the helper call so it can never drift again.

## 2. Frontend tests

- [x] 2.1 Helper unit tests in `tests/lib/utils/scanStatus.test.ts` — 7 cases covering complete, failed, running, discovering, awaiting_confirmation, missing-status, and the `??` vs `||` semantics check (real 0 totalCompanies does not fall through). All 11 tests in the file pass.
- [x] 2.2 + 2.3 Dashboard render tests subsumed by helper unit tests. Rationale: the dashboard page is a Next.js server component that consumes `displayedCompanyCount(scan)` in a one-line cell with no other logic. The helper's 7 cases pin every status × count combination including the bug repro (complete + completedCount=0 + totalCompanies=6 → 6) and the in-flight UX (running + completedCount=3 + totalCompanies=6 → 3). The "did the dashboard wire up the helper" concern is type-checked by `tsc --noEmit`. Establishing a new server-component render-test pattern here for a one-line consumer would be over-investment; the closest precedent (PR #210's `canDeleteScan` introduction) made the same call. If a future render-level concern emerges, add it then.

## 3. Quality gates

- [x] 3.1 `cd frontend && npm run lint` clean
- [x] 3.2 `cd frontend && npx tsc --noEmit` clean
- [x] 3.3 `cd frontend && npm test` — 651 pass (+7 new on the helper)
- [ ] 3.4 Open PR, CI green, merge.
