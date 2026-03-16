# P3: Document Upload — Gap Analysis (Plan vs PR #24)

Generated: 2026-03-16

## Gap #1 — S3 Bucket Infrastructure (NOT IMPLEMENTED)

| Plan | Implementation |
|------|---------------|
| New S3 bucket `janus-documents-{environment}` in `janus_stack.py` | Not added. No S3 bucket, no `DOCUMENTS_BUCKET` env var in CDK |
| `DOCUMENTS_BUCKET` env var passed to both Lambdas | Not added |
| S3 lifecycle rule (90-day expiration) | Not added |
| Lambda IAM permissions for S3 read + presigned URL | Not added |
| `s3.BlockPublicAccess.BLOCK_ALL` | Not added |
| `docker-compose.e2e.yml` — add `s3` to LocalStack `SERVICES` | Not added — still `sqs,dynamodb` |

**Severity:** HIGH
**Impact:** The base64 path works for files under ~6MB (API Gateway limit). Larger files will fail in production. The plan explicitly chose S3 presigned URLs because "Lambda has 6MB payload limit — can't pass file bytes through API Gateway."

---

## Gap #2 — Presigned URL Route (REMOVED)

| Plan | Implementation |
|------|---------------|
| `POST /api/analysis/{id}/upload-url` → returns presigned PUT URL | Removed during architecture review |
| Frontend uploads directly to S3, then calls `/documents` with `documentKey` | Frontend always sends base64 inline |
| `_handle_create_document` downloads from S3 via `documentKey` | S3 path removed — only base64 `fileContent` accepted |

**Severity:** MEDIUM
**Impact:** The plan's data flow diagram shows `Frontend → presigned URL → S3 → POST /documents`. The implementation is `Frontend → base64 → POST /documents`. This is a deliberate simplification but diverges from the plan's architecture decision.

---

## Gap #3 — `company_analysis_factory.py` (NOT MODIFIED)

| Plan | Implementation |
|------|---------------|
| "CompanyAnalysisFactory — pass `document_text` to CompanyAccessor" | Not modified. `document_text` is passed via `factories_factory.py` directly to the `Company` model, bypassing `CompanyAnalysisFactory` |

**Severity:** LOW
**Impact:** None functionally — the `document_text` reaches the model via a different (shorter) path through `factories_factory.py`. But the plan's routing doesn't match reality.

---

## Gap #4 — Prompt Injection Method

| Plan | Implementation |
|------|---------------|
| `doc_section` appended after `format()` call: `user_prompt = _USER_PROMPT_TEMPLATE.format(...) + doc_section` | `{document_section}` is a placeholder inside the template, injected via `.format()` |

**Severity:** LOW
**Impact:** Minor — both approaches work. The implementation is cleaner (single `format()` call).

---

## Gap #5 — Frontend Proxy Route Paths

| Plan | Implementation |
|------|---------------|
| `POST /api/proxy/analysis/[analysisId]/upload-url` | Not created (upload-url route removed) |
| `POST /api/proxy/analysis/[analysisId]/documents` | `POST /api/analysis/[analysisId]/documents` (no `/proxy/` prefix) |
| `DELETE /api/proxy/analysis/[analysisId]/documents/[documentId]` | `DELETE /api/analysis/[analysisId]/documents/[documentId]` (no `/proxy/` prefix) |
| `POST /api/proxy/analysis/[analysisId]/reanalyze` | `POST /api/analysis/[analysisId]/reanalyze` (no `/proxy/` prefix) |

**Severity:** LOW
**Impact:** None — the existing codebase uses `/api/analysis/...` not `/api/proxy/...`. The plan had the wrong prefix.

---

## Gap #6 — E2E Tests for Document Upload ~~(NOT ADDED)~~ FIXED

| Plan | Implementation |
|------|---------------|
| `scripts/e2e-test.sh` — "Add document upload + re-analyze E2E tests" | **FIXED** — Added steps 8d-8f: presigned URL upload, document registration, verify in analysis, re-analyze, delete document |

**Severity:** ~~HIGH~~ RESOLVED

---

## Gap #7 — Missing `company_name` in Reanalyze SQS Message

| Plan | Implementation |
|------|---------------|
| Not explicitly specified in plan | `_handle_reanalyze` sends SQS message without `company_name` field |

**Severity:** LOW
**Impact:** The worker's `_process_reanalysis` log says "Re-analyzing %s with documents" but only shows `analysis_id`, not the company name. The company name will also be silently overwritten by whatever the AI re-extracts.

---

## Gap #8 — Reanalysis Result Deletion Ordering — FIXED

| Plan | Implementation |
|------|---------------|
| Step 3: "Run pipeline", Step 4: "Delete old assessment results" | **FIXED** — Old results now deleted only after pipeline succeeds. On failure, old results preserved. |

**Severity:** ~~HIGH~~ RESOLVED

---

## Gap #9 — Re-analysis Frontend UX — Polling ~~(NOT IMPLEMENTED)~~ FIXED

| Plan | Implementation |
|------|---------------|
| "Re-analyze button triggers POST, then polls scan status until complete, then refreshes data" | **FIXED** — After POST, polls `/api/analysis/{id}` every 3s (max 2 min) until `analyzedAt` timestamp changes, then refreshes. AbortController cleans up on unmount. Consecutive error tracking (3 failures = abort). |

**Severity:** ~~MEDIUM~~ RESOLVED

---

## Gap #10 — `_handle_get_analysis` Documents Format

| Plan | Implementation |
|------|---------------|
| Return `[{ id, filename, fileType, charCount, uploadedAt }]` | `get_documents()` returns camelCase keys — matches plan |

**Severity:** NONE — matches.

---

## Gap #11 — Files Listed in Plan But Not Modified

| File in Plan | Status |
|-------------|--------|
| `backend/src/pipeline/pipeline_factories/company_analysis_factory.py` | Not modified (see gap #3) |
| `infrastructure/stacks/janus_stack.py` | Not modified (see gap #1) |
| `scripts/e2e-test.sh` | Not modified (see gap #6) |
| `scripts/mock_ai_server.py` | Plan says "No change needed" — correct |

---

## Gap #12 — `DOCUMENTS_BUCKET` Env Var in Docker-Compose

| Plan | Implementation |
|------|---------------|
| Both `docker-compose.yml` and `docker-compose.e2e.yml` should include `DOCUMENTS_BUCKET` | Neither updated |

**Severity:** LOW (blocked by gap #1)
**Impact:** When S3 is eventually added, both compose files need updating.

---

## Summary by Severity

| Severity | Gap | Description |
|----------|-----|-------------|
| HIGH | #1 | S3 bucket not in infrastructure — 6MB payload limit in production |
| ~~HIGH~~ FIXED | #8 | ~~Delete-before-pipeline ordering~~ Now deletes after success |
| ~~HIGH~~ FIXED | #6 | ~~No E2E tests~~ Added presigned URL upload + re-analyze E2E tests |
| ~~MEDIUM~~ FIXED | #2 | ~~Presigned URL route removed~~ S3 presigned URL support restored |
| ~~MEDIUM~~ FIXED | #9 | ~~No polling~~ Polls analysis endpoint until results change |
| LOW | #3 | `company_analysis_factory.py` not modified (different routing) |
| LOW | #4 | Prompt injection method differs (cleaner approach used) |
| LOW | #5 | Proxy route path prefix differs (matches existing codebase) |
| LOW | #7 | Missing `company_name` in reanalyze SQS message |
| LOW | #12 | Docker-compose not updated (blocked by #1) |
