## Why

When a company analysis fails during a portfolio scan (AI timeout, unreachable website, insufficient data), the portfolio grid displays "Analyzing... / Analysis failed" with no company name, no error detail, and clicking the card navigates to a page-not-found. The user has zero recoverability — they can't tell which company failed, why it failed, or do anything about it.

Root cause: the company record is only fully populated by `PersistResults` (the final pipeline step). On failure, the record contains only `{id, error}` — no `company_name`, no `company_url`, no `scan_id`. This breaks:
1. **Display**: frontend falls back to "Analyzing..." when `companyName` is empty.
2. **Retry**: the existing `POST /api/analysis/{id}/reanalyze` endpoint reads `company_url` from the record and returns 400 ("no company URL") because it was never written.
3. **Navigation**: the analysis detail page expects a full record and 404s when it only finds an error stub.

This is the #1 usability issue on the portfolio page — every large scan has 3-8 failures, and each one is a dead end.

## What Changes

### Backend

- **Write company identity at pipeline start**: before the first pipeline step runs, persist `company_name`, `company_url`, `scan_id`, and `org_id` to the company record. This ensures even failed analyses have identity. One-line change in `SQSHandler._process_new_analysis` (or in the `JanusRequestExecutor` setup).
- **No changes to the reanalyze endpoint or worker path**: `handle_reanalyze` + `_process_reanalysis` already re-run the pipeline for a single `analysis_id`, preserve the `scan_id` link, and update portfolio scan progress on completion. Once `company_url` is populated, the existing path works for failed analyses too.

### Frontend

- **Portfolio grid card**: show real company name (now populated) instead of "Analyzing..." for failed analyses. Show the error message or a human-readable summary. Card remains clickable → navigates to `/analysis/{id}`.
- **Analysis detail page (`/analysis/{id}`)**: add a **failed state** branch. When the record has `error` and no `analyzedAt`:
  - Display company name, URL, and the error message with a human-readable explanation.
  - Show an **optional document upload zone** (10-K, pitch deck, etc.) — user can provide supplementary data before retrying.
  - Show a **"Retry Analysis"** button that calls `POST /api/analysis/{id}/reanalyze`.
  - After clicking retry, show a progress indicator on the same page. When the pipeline succeeds, the page transitions to the full analysis view. If it fails again, it shows the updated error.
- **Portfolio context preserved**: retry results land back in the portfolio grid via the existing `scan_id` link. The portfolio progress bar updates via `_update_scan_progress`. No separate standalone scan is created.

## Capabilities

### New Capabilities
- `failed-analysis-detail`: failed state on the analysis detail page with error display, optional document upload, and per-company retry button. The retry re-runs the pipeline for that single company within the portfolio context.

### Modified Capabilities
_(No existing specs to modify.)_

## Impact

- **Modified**: `backend/src/handlers/sqs_handler.py` — write company identity at pipeline start in `_process_new_analysis`
- **Modified**: `frontend/src/app/(authenticated)/portfolio/[scanId]/PortfolioView.tsx` — failed card renders real name + error
- **Modified**: `frontend/src/app/(authenticated)/analysis/[id]/` — analysis detail page gains failed-state branch with retry + document upload
- **Reused (no change)**: `POST /api/analysis/{id}/reanalyze` endpoint, `_process_reanalysis` worker path, document upload flow, `_update_scan_progress` portfolio integration
- **No infrastructure changes**: existing SQS queue, worker Lambda, DynamoDB schema all sufficient
- **Tests**: backend unit tests for identity-at-start write; frontend tests for failed-state rendering, retry button interaction, and document upload zone
