# P3: Document Upload & Re-analysis — Implementation Plan

## Overview

Users upload investment memos, CIMs, or diligence docs against an existing analysis. Document text is extracted server-side, stored in DynamoDB, and injected into the AI pipeline's profile extraction step alongside scraped website content. A "re-analyze" action re-runs the full pipeline with the enriched context.

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| File storage | S3 bucket (new) | Lambda has 6MB payload limit — can't pass file bytes through API Gateway. S3 presigned URLs bypass this. |
| Text extraction | Python `pypdf`, `python-docx`, `openpyxl` | Pure Python, no native deps, Lambda-compatible |
| Re-analysis trigger | SQS (same queue) | Reuses existing async worker pattern. Re-analysis is identical to initial analysis but with document text injected. |
| Document metadata | DynamoDB items under assessment PK | Consistent with single-table design. `PK=ASSESSMENT#{id}, SK=DOC#{doc_id}` |

## Data Flow

```
Upload:  Frontend → presigned URL → S3 → POST /api/analysis/{id}/documents (metadata + extract)
                                                ↓
                                    Worker extracts text from S3 object
                                    Stores metadata + extracted_text in DynamoDB
                                                ↓
Re-analyze:  POST /api/analysis/{id}/reanalyze → SQS message (with reanalyze flag)
                                                ↓
                                    Worker fetches doc text from DynamoDB
                                    Injects into ExtractProfile prompt
                                    Runs full 6-step pipeline
                                    Replaces old results
```

---

## Changes by Layer

### 1. Infrastructure — S3 Bucket (`infrastructure/stacks/janus_stack.py`)

Add an S3 bucket for document uploads. Grant both Lambdas read access; API Lambda gets presigned URL generation permission.

```python
bucket = s3.Bucket(self, "DocumentsBucket",
    bucket_name=f"janus-documents-{environment}",
    removal_policy=config["removal_policy"],
    auto_delete_objects=environment == "development",
    block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
    encryption=s3.BucketEncryption.S3_MANAGED,
    lifecycle_rules=[s3.LifecycleRule(expiration=Duration.days(90))],
)
```

Environment variable: `DOCUMENTS_BUCKET` passed to both Lambdas.

### 2. Backend — New Dependencies (`pyproject.toml`)

```
"pypdf>=4.0",
"python-docx>=1.0",
"openpyxl>=3.1",
```

### 3. Backend — Text Extraction Module (`src/documents/extract_text.py`)

New module with:
- `extract_text(file_bytes: bytes, file_type: str) -> str` — dispatcher by file type
- `_extract_pdf(data: bytes) -> str` — via pypdf
- `_extract_docx(data: bytes) -> str` — via python-docx
- `_extract_xlsx(data: bytes) -> str` — via openpyxl (all sheets as text)
- `_extract_text_plain(data: bytes) -> str` — UTF-8 decode
- Per-document cap: 15,000 chars
- Supported types: `pdf`, `docx`, `xlsx`, `xls`, `txt`, `csv`, `md`

### 4. Backend — DynamoDB Document Storage (`src/repositories/dynamodb/assessment_repository.py`)

New methods on `AssessmentRepository`:

```python
def save_document(self, assessment_id: str, document: dict[str, Any]) -> None:
    """Save document metadata + extracted text. Key: PK=ASSESSMENT#{id}, SK=DOC#{doc_id}"""

def get_documents(self, assessment_id: str) -> list[dict[str, Any]]:
    """List all documents for an assessment (SK begins_with DOC#)"""

def delete_document(self, assessment_id: str, document_id: str) -> None:
    """Delete a single document"""

def get_combined_document_text(self, assessment_id: str) -> str:
    """Fetch all docs, concatenate extracted_text with --- separators, cap at 25K chars"""
```

### 5. Backend — API Endpoints (`src/handlers/api_gateway_handler.py`)

Four new routes:

| Method | Path | Auth | Handler |
|--------|------|------|---------|
| `POST` | `/api/analysis/{analysis_id}/upload-url` | Protected | `_handle_upload_url` — returns S3 presigned PUT URL |
| `POST` | `/api/analysis/{analysis_id}/documents` | Protected | `_handle_create_document` — downloads from S3, extracts text, saves metadata |
| `DELETE` | `/api/analysis/{analysis_id}/documents/{document_id}` | Protected | `_handle_delete_document` |
| `POST` | `/api/analysis/{analysis_id}/reanalyze` | Protected | `_handle_reanalyze` — enqueues SQS message with `reanalyze: true` flag |

**`_handle_upload_url`**: Generates presigned PUT URL for `s3://{bucket}/uploads/{analysis_id}/{uuid}.{ext}`. Returns `{ uploadUrl, documentKey }`. Frontend uploads directly to S3.

**`_handle_create_document`**: After frontend uploads to S3, this endpoint:
1. Downloads the file from S3 using the `documentKey`
2. Extracts text via `extract_text()`
3. Saves document record to DynamoDB
4. Returns `{ id, filename, fileType, charCount }`

**`_handle_reanalyze`**: Validates analysis exists and belongs to user's org. Sends SQS message with `{ reanalyze: true, analysis_id, org_id, user_id }`. Returns `{ status: "queued" }`.

### 6. Backend — SQS Worker Changes (`src/handlers/sqs_handler.py`)

Update `_process_message` to handle re-analysis messages:

```python
if message.get("reanalyze"):
    self._process_reanalysis(message)
else:
    # existing flow
```

**`_process_reanalysis`**:
1. Fetch existing analysis to get company URL
2. Fetch combined document text from DynamoDB
3. Run pipeline with `document_text` parameter
4. Delete old assessment results (risks, opportunities, EBITDA tree)
5. Pipeline persists new results under same assessment ID

### 7. Backend — Pipeline Changes

**`FactoryManager.run_company_analysis()`** — add optional `document_text: str | None = None` parameter, pass through to factory.

**`CompanyAnalysisFactory`** — pass `document_text` to `CompanyAccessor`.

**`CompanyAccessor`** — add `get_document_text() -> str | None` and `set_document_text()`.

**`Company` model** — add `document_text: str | None = None` (transient, not persisted).

**`ExtractProfile.execute()`** — inject document text into prompt:
```python
document_text = accessor.get_document_text()
doc_section = ""
if document_text:
    doc_section = (
        "\n\nSUPPLEMENTARY DOCUMENTS (investment memos, diligence docs, etc.):\n"
        f"{document_text[:25000]}\n"
    )
user_prompt = _USER_PROMPT_TEMPLATE.format(
    url=actual_url,
    content=scraped_text[:12000],
) + doc_section
```

### 8. Backend — Analysis Response Change

**`_handle_get_analysis`** — include documents list in response:
```python
documents = assessment_repo.get_documents(assessment_id)
# Add to response: "documents": [{ id, filename, fileType, charCount, uploadedAt }]
```

### 9. Frontend — Types (`src/lib/types/api.ts`)

```typescript
export interface DocumentInfo {
    id: string
    filename: string
    fileType: string
    charCount: number
    uploadedAt: string
}

// Add to AnalysisData:
documents?: DocumentInfo[]
```

### 10. Frontend — DocumentUpload Component (`src/components/DocumentUpload.tsx`)

New component with:
- Drag-and-drop zone (native drag events)
- File type validation (PDF, DOCX, XLSX, TXT, CSV, MD)
- Max 10MB per file
- Upload flow: get presigned URL → PUT to S3 → POST metadata → refresh
- Document list with delete buttons
- "Re-analyze with Documents" button
- Loading/error states

### 11. Frontend — AnalysisDetail Integration

Add `<DocumentUpload>` section to `AnalysisDetail.tsx` below the existing sections. Only visible when viewing your own analysis (authenticated). Re-analyze button triggers POST, then polls scan status until complete, then refreshes data.

### 12. Frontend — Proxy Routes

- `POST /api/proxy/analysis/[analysisId]/upload-url` → backend
- `POST /api/proxy/analysis/[analysisId]/documents` → backend
- `DELETE /api/proxy/analysis/[analysisId]/documents/[documentId]` → backend
- `POST /api/proxy/analysis/[analysisId]/reanalyze` → backend

---

## Files Modified/Created

| File | Action |
|------|--------|
| `infrastructure/stacks/janus_stack.py` | Add S3 bucket + permissions |
| `backend/pyproject.toml` | Add pypdf, python-docx, openpyxl |
| `backend/src/documents/__init__.py` | New package |
| `backend/src/documents/extract_text.py` | New — text extraction logic |
| `backend/src/models/model_company.py` | Add `document_text` field |
| `backend/src/facades/company_accessor.py` | Add document_text getter/setter |
| `backend/src/repositories/dynamodb/assessment_repository.py` | Add document CRUD methods |
| `backend/src/handlers/api_gateway_handler.py` | Add 4 new routes |
| `backend/src/handlers/sqs_handler.py` | Handle reanalyze messages |
| `backend/src/handlers/factory_manager.py` | Pass document_text through |
| `backend/src/pipeline/pipeline_steps/extract_profile.py` | Inject doc text into prompt |
| `backend/src/pipeline/pipeline_factories/company_analysis_factory.py` | Pass document_text |
| `frontend/src/lib/types/api.ts` | Add DocumentInfo type |
| `frontend/src/components/DocumentUpload.tsx` | New — upload UI |
| `frontend/src/app/analysis/[analysisId]/AnalysisDetail.tsx` | Integrate DocumentUpload |
| `frontend/src/app/api/proxy/analysis/[analysisId]/upload-url/route.ts` | New proxy |
| `frontend/src/app/api/proxy/analysis/[analysisId]/documents/route.ts` | New proxy |
| `frontend/src/app/api/proxy/analysis/[analysisId]/documents/[documentId]/route.ts` | New proxy |
| `frontend/src/app/api/proxy/analysis/[analysisId]/reanalyze/route.ts` | New proxy |
| `scripts/mock_ai_server.py` | No change needed (same AI responses) |
| `scripts/e2e-test.sh` | Add document upload + re-analyze E2E tests |

## Test Plan

| Layer | Tests |
|-------|-------|
| `tests/unit/documents/test_extract_text.py` | PDF/DOCX/XLSX/TXT extraction, char cap, unsupported type error |
| `tests/unit/repositories/test_assessment_repository.py` | save/get/delete document, get_combined_document_text |
| `tests/unit/handlers/test_api_gateway_handler.py` | upload-url, create-document, delete-document, reanalyze endpoints |
| `tests/unit/handlers/test_sqs_handler.py` | Reanalyze message processing |
| `tests/unit/pipeline/test_extract_profile.py` | Prompt includes doc text when present, omits when absent |
| `frontend/src/tests/components/DocumentUpload.test.tsx` | Render, upload flow, delete, re-analyze button states |
| `scripts/e2e-test.sh` | Upload doc → re-analyze → verify updated results |

## Suggested Implementation Order

1. Backend text extraction + DynamoDB document storage + tests
2. API endpoints + SQS reanalyze flow + tests
3. Pipeline integration (ExtractProfile doc injection) + tests
4. Frontend component + proxy routes + tests
5. Infrastructure (S3 bucket) + E2E tests

## Verification

```bash
# Backend
cd backend && uv run pytest tests/ -q  # all tests pass, ≥95% coverage
uv run ruff check src/ && uv run pyright src/

# Frontend
cd frontend && npm test && npm run lint && npx tsc --noEmit

# E2E
GH_TOKEN=$(gh auth token) docker compose -f docker-compose.e2e.yml up --build -d
./scripts/e2e-test.sh
```

## Reference

Based on Zack's prototype in `~/Documents/github/pe-scan`:
- Upload endpoint: `src/app/api/analysis/[analysisId]/documents/route.ts`
- Text extraction: `src/lib/documents/extractText.ts`
- Re-analyze endpoint: `src/app/api/analysis/[analysisId]/reanalyze/route.ts`
- UI component: `src/components/DocumentUpload.tsx`
- Prompt injection: `src/lib/ai/prompts.ts` (buildProfilePrompt with documentText param)
