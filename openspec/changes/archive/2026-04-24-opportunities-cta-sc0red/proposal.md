## Why

The AI Opportunities list ends each opportunity card with a section titled **"Implementation Partners"** — a row of neutral gray badges listing third-party vendors (e.g. "Accenture - AI strategy", "Datadog - Observability"). Two problems:

1. **Label positions sc0red as one of many interchangeable vendors.** The phrase "Implementation Partners" reads like procurement metadata, not a value prop. It hides the fact that sc0red — the company producing this analysis — is the implementation partner.
2. **Lowest-energy element on the page.** The section sits last in the expanded card, styled identically to the `strategic_category` chip in the header. It blends into metadata noise. By the time readers reach it, reading momentum is spent and there's no call to action — just a list of vendor names.

We want to reposition sc0red as *the* implementation partner while the reader is at peak interest (after seeing all opportunities), without being noisy (not repeated on every card).

## What Changes

The change ships in **two phases**:

### Phase 1 — Frontend reposition (PR #178, in flight)

- **Relabel "Implementation Partners" → "Tech Stack"** on each opportunity card as an interim step. Vendor chips remain visible so the existing backend data still has a home while Phase 2 is in flight.
- **Add a single expandable sc0red CTA banner** at the bottom of the `OpportunitiesList`. Collapsed by default — one line with a chevron. Expanded — pitch copy + an external link to the sc0red contact page.
- **Make the contact URL env-configurable** via `NEXT_PUBLIC_SC0RED_CONTACT_URL`, defaulting to `https://www.sc0red.com/contact`. Trivial to swap per environment or rebrand later.
- **Mirror the changes in the PDF export** (`/api/export/pdf/[analysisId]`). The PDF version renders the pitch inline (non-interactive) and uses "Tech Stack" labels. A single sc0red block closes the opportunities section.

### Phase 2 — Backend removal (follow-up PR)

The original intent was to *replace* third-party implementation partner framing with sc0red branding — not rename it. Keeping the backend generating `related_services` indefinitely wastes AI tokens, storage, and bandwidth on a field we're actively de-emphasizing. Phase 2 removes the field end-to-end:

- **AI pipeline**: drop `related_services` from the `detail.json` schema, remove the "up to 3 vendor recommendations" instruction from the prompt template and system prompt, and stop extracting the field in `DetailOpportunity` / `PersistResults` steps.
- **Domain model**: remove `related_services` from the `Opportunity` Pydantic model (`src/models/model_company.py`).
- **Storage**: stop writing/reading the field in `assessment_repository.py` (save, batch_save, get). Existing rows in DynamoDB retain the attribute; reads simply ignore it (no migration required).
- **Mock AI server**: remove from `scripts/mock_ai_server.py` so E2E tests don't simulate a field that no longer exists.
- **Frontend**: drop the "Tech Stack" section entirely from `OpportunitiesList.tsx` and the PDF export; remove `related_services` from the `Opportunity` TypeScript type; clean up fixtures/assertions in affected tests.
- **Docs**: remove the field from `docs/api.md`.

Expected wins: ~50–100 tokens saved per scan, one fewer field to maintain, smaller API responses, and a frontend that leads with the sc0red CTA without competing signal from vendor chips.

## Capabilities

### New Capabilities
- `opportunities-cta`: A single sc0red call-to-action rendered at the bottom of the opportunities list and PDF export, with "Tech Stack" relabeling on each opportunity card.

### Modified Capabilities
(none)

## Impact

- **Files modified**: `frontend/src/components/OpportunitiesList.tsx`, `frontend/src/app/api/export/pdf/[analysisId]/route.ts`, `frontend/src/tests/components/OpportunitiesList.test.tsx`
- **Files added**: `frontend/src/components/Sc0redCTABanner.tsx`, `frontend/src/tests/components/Sc0redCTABanner.test.tsx`
- **Env var added**: `NEXT_PUBLIC_SC0RED_CONTACT_URL` (documented in `frontend/.env.local.example`). The resolver reads it at code level with a safe default. Per-environment override at the CDK / Amplify branch level is a fast-follow — not wired in this PR. The default URL is the production URL, so all deployed builds resolve correctly today.
- **No backend changes**: The `related_services` field and its schema stay exactly as they are — this is a pure presentation-layer change.
- **No data migration**: Existing analyses already stored in DynamoDB render correctly under the new labels.

## Non-Goals

- **No CTA click analytics.** Deferred to the companion proposal `opportunities-cta-analytics`.
- **No A/B testing.** Single treatment, ships everywhere at once.
- **No changes to what `related_services` contains.** The underlying vendor list stays as-is — we only change how it's labeled and where it appears next to a sc0red pitch.
- **No rebrand of the rest of the UI.** This proposal is scoped to the opportunities list and the PDF export that mirrors it.
- **No per-card sc0red hook.** We explicitly considered a per-card "sc0red implements this →" line in the collapsed header and rejected it — too repetitive on scans with many opportunities.
