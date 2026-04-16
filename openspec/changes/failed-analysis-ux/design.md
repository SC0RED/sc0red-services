## Context

Current company record lifecycle:

```
SQS message arrives (has: url, company_name, scan_id, request_id)
  │
  ├─ _report_progress writes: {pipeline_progress: N}   ← no identity
  │
  ├─ Pipeline runs (6 steps)
  │
  ├─ SUCCESS: PersistResults writes full record          ← identity here
  │     (company_name, company_url, risk_score, etc.)
  │
  └─ FAILURE: _record_failure writes: {error: "..."}    ← no identity
        → card shows "Analyzing..." / "Analysis failed"
        → click → 404
        → retry endpoint returns 400 ("no company URL")
```

After fix:

```
SQS message arrives (has: url, company_name, scan_id, request_id)
  │
  ├─ Worker writes identity FIRST:                       ← NEW
  │     {company_name, company_url, scan_id, org_id}
  │
  ├─ Pipeline runs (6 steps)
  │
  ├─ SUCCESS: PersistResults overwrites with full record
  │     (same fields + risk_score, analyzedAt, etc.)
  │
  └─ FAILURE: _record_failure writes: {error: "..."}
        → card shows "Endurance Lift" / "Analysis failed"  ✓
        → click → failed-state detail page                  ✓
        → retry endpoint reads company_url → works          ✓
```

## Goals / Non-Goals

**Goals:**
- Failed company analyses show their real name and URL in the portfolio grid and on the detail page.
- Users can retry individual failed analyses from the detail page, with optional document upload.
- Retry results land back in the portfolio scan (same `scan_id` link, portfolio progress updates).
- The existing reanalyze endpoint and worker path are reused without modification.

**Non-Goals:**
- Bulk retry ("retry all failed") — useful but adds UX complexity. Defer.
- Automatic retry on failure — that's issue #2 (pipeline retry/backoff), separate concern.
- Error message categorization (temporary vs permanent failure) — polish for later.
- Changing the analysis detail page layout for successful analyses — out of scope.

## Decisions

### Decision 1: Write identity in `_process_new_analysis`, not in the pipeline

**Decision**: add a `company_repo.update(request_id, {...})` call in `SQSHandler._process_new_analysis` before calling `run_company_analysis`, not inside `JanusRequestExecutor` or a new pipeline step.

**Why**: the SQS message has `company_name` and `url` as top-level fields. The worker already unpacks them. Writing from the worker keeps the pipeline steps pure (they don't know about DynamoDB) and matches the existing `_record_failure` pattern (also in the worker, not the pipeline).

**Alternative considered**: new "InitializeCompanyRecord" pipeline step as step 0. Rejected — couples pipeline steps to DynamoDB, violates the existing pattern where only `PersistResults` writes to the repository.

### Decision 2: Reuse `/analysis/{id}` page with state branching, not a separate route

**Decision**: the analysis detail page renders two states based on the company record:
- `analyzedAt` present → full analysis view (existing)
- `error` present, no `analyzedAt` → failed state (new)

**Why**: natural transition — if the user retries and it succeeds, the same URL shows the results without navigation. Avoids a redirect chain or a new route.

### Decision 3: Retry calls the existing reanalyze endpoint

**Decision**: the "Retry Analysis" button calls `POST /api/analysis/{id}/reanalyze`. No new endpoint.

**Why**: the endpoint already:
- Re-runs the pipeline with the same `analysis_id` and `scan_id`
- Fetches any uploaded documents before running
- Updates scan progress on completion
- Handles success (overwrite) and re-failure (update error) correctly

The only prerequisite was that `company_url` exists on the record — solved by Decision 1.

### Decision 4: Document upload is optional, happens before retry

**Decision**: the failed-state page shows a drop zone for documents. Upload stores the file in S3 + creates a document record in DynamoDB (existing upload flow). When the user clicks "Retry Analysis", the reanalyze worker fetches the document text automatically.

**Why**: this matches the existing re-analysis-with-documents flow exactly. The upload and the retry are decoupled — user can retry without uploading, or upload then retry.

### Decision 5: Portfolio grid card shows company name + error badge

**Decision**: failed cards in the portfolio grid show:
- Company name (from the now-populated `companyName` field)
- A red "Failed" badge (replacing "Analysis failed" text)
- Clicking navigates to the failed-state detail page

**Why**: matches the visual weight of successful cards (name + score + badge) but with a clear error signal. "Analyzing..." is reserved for genuinely in-progress analyses.

## Risks / Trade-offs

- **[Risk] `PersistResults` overwrites identity fields on success.** If PersistResults writes a different `company_name` than what the SQS message had (e.g., pipeline resolves "Endurancelift" → "Endurance Lift Solutions Inc."), the initial worker-written name is overwritten. This is correct behavior — the pipeline-resolved name is better.
- **[Risk] Document upload on a never-completed analysis.** The upload flow writes to the assessment record. For a failed analysis, there may be no assessment record yet. Need to verify the upload path creates one if absent.
- **[Trade-off] Failed cards still take up grid space.** In a 69-company portfolio with 8 failures, those 8 cards sit alongside 61 successful ones. Alternative: collapse failures into a summary section at the bottom. Deferred — current approach is simpler and lets users retry inline.
- **[Trade-off] Raw error messages may confuse non-technical users.** "AI provider timeout" means nothing to a PE analyst. Deferred — categorize errors later with user-facing copy.

## Open Questions

- Should the retry button be disabled while a retry is in progress (to prevent double-send)? **Recommendation**: yes, switch to a spinner + "Retrying..." state after click.
- Should we show retry count? ("Failed 2 times, last error: ...") **Recommendation**: not in v1. Track it later if repeat failures become common.
