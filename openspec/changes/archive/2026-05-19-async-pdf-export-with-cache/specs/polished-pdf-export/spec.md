## MODIFIED Requirements

### Requirement: Export PDF returns a binary PDF, not HTML

The export-PDF surface SHALL return a binary PDF document with ``Content-Type: application/pdf`` and a ``Content-Disposition: attachment`` header carrying a sensible filename derived from the company name and analysis date.

The export endpoint SHALL be ``POST /api/export/pdf/<analysisId>`` (the prior synchronous ``GET`` route is removed in Phase 4). The endpoint behaviour depends on the analysis's ``pdfExport`` sub-record:

- **If ``pdfExport.status == "ready"``** — the response is ``200 OK`` with a JSON body ``{status: "ready", url: <presigned-s3-url>, generatedAt: <iso>}``. The frontend then redirects the browser to ``url``; the browser downloads the PDF bytes from S3 directly.
- **If ``pdfExport`` is absent, ``status == "failed"``, or ``status == "rendering"`` but stale (older than 60 s)** — the endpoint async-invokes the PDF render Lambda, writes ``pdfExport.status = "rendering"`` + ``started_at`` to the analysis record, and returns ``202 Accepted`` with body ``{status: "rendering", startedAt: <iso>}``.
- **If ``pdfExport.status == "rendering"`` and not stale** — the endpoint returns ``202 Accepted`` without enqueuing a duplicate render (idempotent dedup via the data layer).

The presigned S3 URL SHALL expire within 60 seconds of issuance. Each ``200`` response mints a fresh URL.

#### Scenario: First-ever export for an analysis kicks off a render

- **WHEN** the user clicks Export PDF on an analysis whose ``pdfExport`` field is absent
- **THEN** the POST endpoint returns ``202 Accepted`` with ``{status: "rendering"}``
- **AND** the analysis record gains ``pdfExport: {status: "rendering", started_at: <now>}``
- **AND** the PDF render Lambda is async-invoked once

#### Scenario: Cached PDF serves instantly on re-click

- **WHEN** the user clicks Export PDF and the analysis's ``pdfExport.status`` is ``"ready"``
- **THEN** the POST endpoint returns ``200 OK`` with ``{status: "ready", url: <presigned-s3-url>}``
- **AND** the browser is redirected to the presigned URL and downloads the cached PDF
- **AND** no PDF render is enqueued

#### Scenario: Concurrent clicks on the same analysis dedupe

- **WHEN** the user clicks Export PDF twice within 1 second on an analysis with no cached PDF
- **THEN** both responses are ``202 Accepted``
- **AND** only one render is enqueued
- **AND** ``pdfExport.started_at`` reflects only the first click

### Requirement: ExportPDFButton shows loading state and triggers download

The ``ExportPDFButton`` component SHALL implement a status-aware flow:

- On click: POST to ``/api/export/pdf/<analysisId>``.
- If the response is ``200 OK`` with ``url``: redirect the browser to ``url`` (which triggers the download via the S3 object's ``Content-Disposition`` header). The button returns to idle.
- If the response is ``202 Accepted``: enter polling state. The button label becomes "Generating PDF…" and the button is disabled.
- Polling: ``GET /api/export/pdf/<analysisId>/status`` at 2-second intervals for up to 10 polls (~20 s), then back off to 5-second intervals.
- When ``status`` flips to ``ready``: the button reads the ``url`` from the status response, redirects the browser, and returns to idle.
- When ``status`` flips to ``failed``: the button shows an error Toast with the ``error`` field text, returns to idle, and is re-clickable.

The "Generating PDF…" toast SHALL include a non-blocking dismiss control so users can leave the page during render and return later to find the PDF ready.

#### Scenario: Button enters polling state on cold render

- **WHEN** the user clicks Export PDF and the response is 202
- **THEN** the button label changes to "Generating PDF…" within 200 ms
- **AND** the button is disabled
- **AND** a polling cycle starts at 2-second intervals

#### Scenario: Button restores idle when ready arrives via polling

- **WHEN** the polling status endpoint returns ``{status: "ready", url: <presigned>}``
- **THEN** the button redirects the browser to the presigned URL
- **AND** the button returns to idle within 500 ms of the redirect

#### Scenario: Failed render surfaces error and re-enables button

- **WHEN** the polling status endpoint returns ``{status: "failed", error: <message>}``
- **THEN** an error Toast displays the ``error`` field text
- **AND** the button returns to idle and is re-clickable
- **AND** the next click re-triggers a fresh render

## ADDED Requirements

### Requirement: Cached PDFs live in a dedicated S3 bucket with per-analysis keying

A new S3 bucket ``janus-<env>-pdf-exports`` SHALL store rendered PDFs. Objects SHALL be keyed by ``pdf-exports/<analysisId>.pdf`` — one object per analysis. Re-renders overwrite the previous object.

The bucket SHALL be configured with:
- Server-side encryption (SSE-S3 minimum).
- Block all public access.
- Bucket-owner-enforced object ownership (no object ACLs).
- No lifecycle policy (storage cost is negligible at expected volume).

The PDF render Lambda SHALL have ``s3:PutObject`` on the bucket. The Python API Lambda SHALL have ``s3:GetObject`` (for minting presigned URLs).

#### Scenario: First render writes a per-analysis S3 object

- **WHEN** the PDF render Lambda successfully renders a PDF for analysis ``<id>``
- **THEN** the bytes are uploaded to ``s3://janus-<env>-pdf-exports/pdf-exports/<id>.pdf``
- **AND** the object is server-side encrypted (SSE-S3)
- **AND** subsequent renders for the same ``<id>`` overwrite the same key

### Requirement: PDF render runs asynchronously via Lambda async-invoke, not synchronously

The Python API Lambda SHALL invoke the PDF render Lambda with ``InvocationType="Event"`` (async-invoke), not ``InvocationType="RequestResponse"``. The async invocation returns immediately with ``StatusCode: 202``; the PDF Lambda runs out-of-band and writes its result to S3 + DynamoDB.

The PDF render Lambda SHALL:
1. Render the PDF as today (Puppeteer + headless Chromium against the print route).
2. ``PutObject`` to the S3 bucket at the per-analysis key.
3. Update the analysis record with a conditional ``UpdateItem``: set ``pdfExport.status = "ready"``, ``pdfExport.generated_at = <now>``, ``pdfExport.s3_key = <key>``. The condition expression SHALL include ``pdfExport.started_at = <the timestamp this Lambda invocation owned>`` so a parallel re-analyse that cleared ``pdfExport`` can't be silently overwritten.
4. On any exception or error: update ``pdfExport.status = "failed"`` + ``pdfExport.error = <message>``.

The PDF render Lambda SHALL have a DLQ configured for async-invoke failures (Lambda's retry budget exhausted). A CloudWatch alarm SHALL fire on any DLQ message.

#### Scenario: Async-invoke returns immediately

- **WHEN** the POST endpoint enqueues a render
- **THEN** the boto3 ``invoke`` call returns within 100 ms
- **AND** the endpoint responds 202 to the frontend within 1 s total
- **AND** the PDF Lambda runs in the background

#### Scenario: PDF Lambda update is conditional on ``started_at`` ownership

- **WHEN** the PDF Lambda completes its render
- **AND** the analysis's ``pdfExport.started_at`` no longer matches the timestamp the Lambda owned (e.g., a re-analyse cleared the field, or a newer render is in flight)
- **THEN** the conditional UpdateItem fails
- **AND** the Lambda logs the conditional-failure and discards its rendered PDF (the S3 object is orphaned; the next render will overwrite the same key)

### Requirement: Status endpoint detects stale rendering and surfaces as failed

``GET /api/export/pdf/<analysisId>/status`` SHALL return the analysis's ``pdfExport`` sub-record, with one adjustment: if ``status == "rendering"`` AND ``now - started_at > 60 seconds``, the response SHALL return ``status: "failed"`` with a synthetic ``error`` field (``"Render appears stuck; try again."``) so the frontend can exit the polling loop. The persisted record is NOT modified by the read; the next POST checks the same stale window and is permitted to re-trigger.

#### Scenario: Stale rendering is reported as failed

- **WHEN** the status endpoint is queried for an analysis with ``pdfExport.status = "rendering"`` and ``started_at = 90 s ago``
- **THEN** the response is ``200`` with ``{status: "failed", error: "Render appears stuck; try again."}``
- **AND** the underlying DynamoDB record is unchanged

#### Scenario: Re-trigger after stale detection writes a fresh ``started_at``

- **WHEN** the user clicks Export PDF after a stale-rendering detection
- **THEN** the POST endpoint treats the existing ``rendering`` state as expired and proceeds as if no ``pdfExport`` existed
- **AND** ``pdfExport.started_at`` is updated to the current timestamp before the Lambda is async-invoked

### Requirement: Re-analyse clears cached PDF + deletes the S3 object

The re-analyse handler SHALL extend its existing clear-pre-pipeline-state logic to include the cached PDF:

1. Read ``analysis.pdfExport`` from the assessment record.
2. If present and ``s3_key`` is set, attempt to ``DeleteObject`` from the S3 bucket (best-effort; log but don't fail re-analyse on S3 errors).
3. Clear the ``pdfExport`` field on the analysis record (``REMOVE`` in DynamoDB).
4. Continue with existing strategy-map clearing + pipeline start.

The PDF Lambda's conditional ``UpdateItem`` (per the prior requirement) protects against the race where re-analyse clears the field mid-render and the Lambda then attempts to write a stale "ready" state.

#### Scenario: Re-analyse with a cached PDF deletes the S3 object

- **WHEN** a re-analyse is triggered on an analysis with ``pdfExport.status = "ready"`` and ``s3_key = "pdf-exports/<id>.pdf"``
- **THEN** the S3 object at ``pdf-exports/<id>.pdf`` is deleted
- **AND** the analysis record's ``pdfExport`` field is cleared
- **AND** the analysis pipeline proceeds as today

#### Scenario: Re-analyse during an in-flight render races safely

- **WHEN** a re-analyse fires while the PDF Lambda is rendering (``pdfExport.status = "rendering"``)
- **THEN** the re-analyse handler clears ``pdfExport`` + attempts S3 delete (no object exists yet, no-op)
- **AND** the PDF Lambda's conditional ``UpdateItem`` fails when it tries to write "ready" because ``pdfExport.started_at`` no longer matches
- **AND** the stale render's PDF (if uploaded) is orphaned in S3 but harmless; it'll be overwritten by the next render of the same analysis
