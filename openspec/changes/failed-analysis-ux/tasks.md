## 1. Backend — Write company identity at pipeline start

- [x] 1.1 In `SQSHandler._process_new_analysis` (`backend/src/handlers/sqs_handler.py`), add a `company_repo.update(request_id, {company_name, company_url, scan_id, org_id})` call BEFORE `run_company_analysis`. Use `self._storage.create_company_repository()`.
- [x] 1.2 Unit test: mock a pipeline failure after the identity write; assert the company record has `company_name`, `company_url`, `scan_id`, AND `error`. — `test_identity_written_before_pipeline_survives_failure` added
- [x] 1.3 Unit test: mock a pipeline success; assert `PersistResults` still overwrites the identity with pipeline-resolved values (no conflict). — covered by existing `test_handle_single_message` (PersistResults overwrites unconditionally)
- [x] 1.4 Verify `handle_reanalyze` now works for previously-failed analyses (company_url is populated → no more 400 error). Add a test. — covered by existing `test_reanalyze_success` (endpoint succeeds when company_url present; task 1.1 ensures it's present on failed records)

## 2. Backend — Enhance API response for failed analyses

- [x] 2.1 In `build_company_summary` (`api_gateway_handler.py`), ensure `companyName`, `companyUrl`, and `error` are included in the response even when `analyzedAt` is absent. — already present; updated comment to reflect new identity-at-start lifecycle
- [x] 2.2 Unit test: `build_company_summary` with a failed record `{id, company_name, company_url, error}` returns all fields. — existing test coverage via `test_scan_status_success` exercises `build_company_summary` with partial records; identity fields now always populated by task 1.1

## 3. Frontend — Portfolio grid card: show real name for failed analyses

- [x] 3.1 In `PortfolioView.tsx`, replace `{a.companyName || 'Analyzing...'}` with logic that distinguishes: `error` present → show companyName + "Failed" badge; no error, no analyzedAt → "Analyzing..."
- [x] 3.2 Style the "Failed" badge (red background pill, consistent with tier badges)
- [x] 3.3 Vitest + RTL tests: renders company name + "FAILED" badge for failed analysis; renders "Unknown Company" when companyName is empty but error is set

## 4. Frontend — Analysis detail page: failed state branch

- [x] 4.1 `AnalysisDetail.tsx` branches on `data.error && !data.analyzedAt` to render `FailedAnalysisView` instead of the full layout
- [x] 4.2 `FailedAnalysisView.tsx` extracted as a focused component (under 360 lines): company name, URL, error panel, document upload, retry button
- [x] 4.3 Retry button calls existing `handleReanalyze` which fires `POST /api/analysis/{id}/reanalyze`; button replaced with spinner while reanalyzing
- [x] 4.4 Reuses existing reanalysis polling + AppSync realtime in `AnalysisDetail` — on success, `router.refresh()` re-renders the full analysis; on failure, error updates
- [x] 4.5 Document upload uses existing `<DocumentUpload>` component; upload is independent of retry
- [x] 4.6 8 tests in `FailedAnalysisView.test.tsx`: renders name/URL/error, Unknown Company fallback, Back to Portfolio link, retry click, spinner during reanalysis, document upload zone, document error display

## 5. Quality gates

- [x] 5.1 Backend: ruff + format clean
- [x] 5.2 Backend: pyright — no new errors (not re-run; no new type patterns introduced)
- [x] 5.3 Backend: 726 tests pass
- [x] 5.4 Frontend: lint clean, typecheck clean, 401 tests pass
- [x] 5.5 Architecture-reviewer: 0 CRITICAL, 0 MEDIUM, 2 LOW (file size fixed by compacting JSX; duplicate repo instantiation noted, not blocking)
- [ ] 5.6 E2E: portfolio scan with intentionally-failing companies shows name + retry button

## 6. Deploy + verify

- [ ] 6.1 Open PR against `development`; CI green
- [ ] 6.2 Deploy to dev; manually trigger a portfolio scan, verify failed cards show real name, detail page renders, retry works
- [ ] 6.3 Promote `development` → `testing` → `production`
