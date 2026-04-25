## 1. Backend — link record schema

- [x] 1.1 Extend `link_company()` in `backend/src/repositories/dynamodb/scan_repository.py` to accept and persist `company_url: str` and `order_index: int` on the `scan_company` link item.
- [x] 1.2 Confirm `get_scan_companies()` returns `company_url` and `order_index` when present and tolerates absence (no KeyError on legacy records).
- [x] 1.3 Update unit tests in `backend/tests/unit/repositories/dynamodb/test_scan_repository.py` covering: write with new fields, read with new fields present, read with new fields absent (legacy fallback).

## 2. Backend — confirm flow writes the new fields

- [x] 2.1 In `handle_scan_confirm` (`backend/src/handlers/scan_handlers.py`), pass `company_url` and the loop index as `order_index` into `link_company()`.
- [x] 2.2 Add a unit test in `backend/tests/unit/handlers/test_scan_handlers.py`: confirm a 3-company scan, assert all three link records have URLs and order_indexes 0/1/2 in submission order.

## 3. Backend — handle_scan_get builds the unified analyses array

- [x] 3.1 Introduce a helper `_build_unified_analyses(scan_companies_links, companies_records) -> list[dict]` that joins links + records on `company_id`, hydrates from the record when present, and synthesizes a pending entry from the link otherwise.
- [x] 3.2 Compute the `state` field per entry: `failed` if `error` set; `done` if `analyzed_at` set; `scanning` if `pipeline_progress > 0`; `pending` otherwise (collapses no-record + progress=0).
- [x] 3.3 Include `companyName`, `companyUrl`, `orderIndex`, `state`, `pipelineLabel`, and the existing fields (`overallRiskScore`, `riskTier`, `analyzedAt`, `error`, `pipelineProgress`) in each entry.
- [x] 3.4 Wire the helper into `handle_scan_get` to replace the current `[build_company_summary(c) for c in companies_batch]` line. The returned `analyses` MUST have length `total_companies` whenever the scan has confirmed.
- [x] 3.5 If `scan_handlers.py` crosses 400 lines after the change, extract `_build_unified_analyses` to `backend/src/utilities/scan_summary.py` and re-import.
- [x] 3.6 Update or remove the now-redundant `_compute_scan_progress` and `_derive_progress_label` helpers if their inputs change; do not regress existing callers.

## 4. Backend — unit tests for the unified analyses builder

- [x] 4.1 Test in `backend/tests/unit/handlers/test_scan_handlers.py` (or equivalent if the helper moves): all-pending case (50 links, 0 records) → 50 pending entries.
- [x] 4.2 Test mixed states: 5 done + 10 scanning + 8 record-but-progress=0 + 27 no-record-yet → 5 done + 10 scanning + 35 pending.
- [x] 4.3 Test failed state: company record with non-empty `error` → entry has `state: "failed"`.
- [x] 4.4 Test legacy fallback: link records without `company_url` / `order_index` → entries serialize with those fields absent or null and the response still validates.
- [x] 4.5 Test ordering: entries are returned in `order_index` ascending order.

## 5. Backend — quality gates

- [x] 5.1 `cd backend && uv run ruff check src/` clean.
- [x] 5.2 `cd backend && uv run pyright src/` no new errors vs baseline (347 = baseline).
- [x] 5.3 `cd backend && uv run pytest tests/ -q` all green; coverage ≥ 95% (816 passed, 95.42%).

## 6. Frontend — type updates

- [x] 6.1 In `frontend/src/lib/types/api.ts`, extend `ScanAnalysis` with `state: 'pending' | 'scanning' | 'done' | 'failed'` and `orderIndex: number | null`.
- [x] 6.2 Search the frontend for any code that reads `analyses` and assumes `length === companies-with-records` — only PortfolioView.tsx; addressed in §7.

## 7. Frontend — PortfolioView state-driven rendering

- [x] 7.1 Replace the current four-way render ladder in the heatmap card with a switch on `a.state`. Define a `StateBadge` (or inline render block) per state: pending, scanning, done, failed.
- [x] 7.2 Replace the `analyses.sort((a,b) => a.id.localeCompare(b.id))` line with a sort by `orderIndex`, falling back to `id` when `orderIndex == null` (legacy scans).
- [x] 7.3 Apply the same state switch to the bottom "All Companies" table — pending rows show "—" for score/tier (today's behavior), scanning rows show the pipeline label in the score column or a dedicated cell, done/failed rows are unchanged.
- [x] 7.4 Remove the now-dead `hasPendingWork` heuristic that checks `analyses.length < totalCompanies` — the array is always full-length now.

## 8. Frontend — pulse animation + a11y

- [x] 8.1 Add a single `@keyframes pulse-dot` definition (1.4s ease-in-out infinite, animates `opacity` from 0.4 → 1.0 → 0.4) to a global stylesheet (or a CSS-module that PortfolioView imports).
- [x] 8.2 Wrap the rule in `@media (prefers-reduced-motion: no-preference) { ... }`, with the matching `(reduce)` block setting fixed opacity 1.0 (no animation). (Global `prefers-reduced-motion` rule already collapses animation-duration → dot freezes at starting opacity 1.0.)
- [x] 8.3 Ensure the dot uses GPU-friendly properties only (`opacity`, `transform`); no `width`/`height` animation, no `box-shadow` keyframes.

## 9. Frontend — unit tests

- [x] 9.1 Vitest test for each of the four `state` values in `frontend/src/tests/components/PortfolioView.test.tsx`: data-state attribute + state-specific DOM treatment.
- [x] 9.2 Test that 50 cards render at t=0 when `analyses.length === 50` and all entries have `state: "pending"`.
- [~] 9.3 `prefers-reduced-motion` test deferred — animation is CSS-only (no JS branch), and the global rule already collapses `animation-duration` to 0.01ms. Asserting `getComputedStyle(...)` on a CSS animation in jsdom is brittle (jsdom doesn't fully implement matchMedia × CSS). The CSS itself is the source of truth and is reviewable. Manual verification covered in §12.2.
- [x] 9.4 Test sort order: 3-entry analyses with unsorted `orderIndex`, asserts orderIndex=0 entry renders first.
- [x] 9.5 Test legacy fallback: entries with `orderIndex: null` sort by id without crashing; mixed legacy + new also works.
- [x] 9.6 Existing tests rewritten to assert state-driven treatment (Pending/pulse-dot/FAILED/score) instead of old "Queued"/"Analyzing..." text inference.

## 10. Frontend — quality gates

- [x] 10.1 `cd frontend && npm run lint` clean.
- [x] 10.2 `cd frontend && npx tsc --noEmit` clean.
- [x] 10.3 `cd frontend && npm test` all green (447 passed).

## 11. Architecture review + E2E

- [ ] 11.1 Run the `architecture-reviewer` agent on the combined backend + frontend diff. Resolve all CRITICAL + MEDIUM findings.
- [ ] 11.2 Run the E2E suite locally per `CLAUDE.md`: `GH_TOKEN=$(gh auth token) docker compose -f docker-compose.e2e.yml up --build -d` then `E2E_MODE=full ./scripts/e2e-test.sh`. All tests must pass.
- [ ] 11.3 Add a new E2E case (or extend an existing portfolio one) that asserts: confirm a scan with N>1 companies → poll once → response `analyses` length equals N → all entries have `state: "pending"` → wait for at least one `done` → assert other entries still present.

## 12. Manual verification before PR

- [ ] 12.1 Local dev: confirm a 5-company portfolio scan; verify 5 cards render at t=0; verify pulse + step label appears on at least one scanning card; verify cards never re-order.
- [ ] 12.2 Verify `prefers-reduced-motion` in DevTools (Rendering panel → Emulate CSS media feature) — pulse stops, step label still renders.
- [ ] 12.3 Verify a failed company shows the FAILED badge in its frozen position.
- [ ] 12.4 Open PR against `development` with self-review; CI green; address review.
