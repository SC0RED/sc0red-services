## 1. Wire env-configurable contact URL

- [x] 1.1 Add `NEXT_PUBLIC_SC0RED_CONTACT_URL` to `frontend/.env.local.example` with the default value `https://www.sc0red.com/contact` and a comment explaining it's optional
- [x] 1.2 Add a resolver to `frontend/src/lib/config.ts` (single-file pattern already used by this module): `getSc0redContactUrl()` returns `process.env.NEXT_PUBLIC_SC0RED_CONTACT_URL` if truthy, otherwise the `SC0RED_CONTACT_URL_DEFAULT` constant. Treat empty string / whitespace as falsy.
- [x] 1.3 Env var is read at code level only. The Amplify build grep (`env | grep -E '^(NEXTAUTH_|BACKEND_URL|NEXT_PUBLIC_)'`) copies any matching env vars from the build environment to `.env.production` — **but** no value is currently injected into the Amplify branch environment via CDK, so the default is used for all deployed builds today. Per-environment override at the CDK level is a fast-follow — see tasks below (section 8).

## 2. Create the sc0red CTA banner component

- [x] 2.1 Create `frontend/src/components/Sc0redCTABanner.tsx` as a client component (`"use client"`)
  - Takes `contactUrl: string` as a prop (keeps the component pure and testable)
  - Collapsed state: single row with ◆ icon + "sc0red can help you capture these opportunities" + chevron
  - Expanded state: same header + pitch paragraph + "Start the conversation →" button styled as a link-button
  - Uses `aria-expanded` + `aria-controls` matching the existing opportunity-card pattern
  - External link uses `target="_blank"` + `rel="noopener noreferrer"`
  - Styling: accent background (distinct from opportunity cards), 3px blue top-border or left-border, uses existing CSS tokens (`var(--bg-surface-3)`, `var(--accent-blue)`, `var(--radius-md)`)
- [x] 2.2 Copy for initial version:
  - **Collapsed heading:** "sc0red can help you capture these opportunities"
  - **Expanded body:** "Our AI specialists implement opportunities like these end-to-end — from strategy through production deployment — moving faster than traditional enterprise timelines."
  - **CTA:** "Start the conversation →"
  - (No timeline commitment — pre-committing without knowing scope is risky. "Faster than traditional enterprise timelines" is confident but non-specific.)

## 3. Wire the banner into OpportunitiesList

- [x] 3.1 In `frontend/src/components/OpportunitiesList.tsx`, import the banner and `getSc0redContactUrl`
- [x] 3.2 Rename the per-card section label from "Implementation Partners" to "Tech Stack" (single literal at line 331)
- [x] 3.3 Render `<Sc0redCTABanner contactUrl={getSc0redContactUrl()} />` after the last opportunity card, gated on `filteredOpps.length > 0`

## 4. Mirror changes in the PDF export

- [x] 4.1 In `frontend/src/app/api/export/pdf/[analysisId]/route.ts` (lines 145-152), rename "Implementation Partners" → "Tech Stack"
- [x] 4.2 After the opportunities loop closes, render a static sc0red CTA block containing:
  - Header: "sc0red can help you capture these opportunities"
  - Body pitch copy (same as the React banner's expanded state)
  - Contact URL rendered as visible text (not just a hyperlink) on its own line
  - Only render the block if the opportunities array is non-empty
- [x] 4.3 Use a dedicated CSS class (e.g. `.sc0red-cta`) defined in the existing inline stylesheet — distinct background, matches the banner's visual weight
- [x] 4.4 Read the contact URL in the PDF route via `process.env.NEXT_PUBLIC_SC0RED_CONTACT_URL || 'https://www.sc0red.com/contact'` (or import `getSc0redContactUrl` if it's SSR-safe)

## 5. Tests

- [x] 5.1 Create `frontend/src/tests/components/Sc0redCTABanner.test.tsx`:
  - Renders the collapsed heading
  - Clicking the trigger toggles `aria-expanded` and reveals the pitch + CTA
  - The CTA link has the passed `contactUrl` as `href`, `target="_blank"`, and `rel` including `noopener` and `noreferrer`
- [x] 5.2 Update `frontend/src/tests/components/OpportunitiesList.test.tsx`:
  - Existing assertion on "Accenture - AI strategy" stays — only the *heading* changes
  - Add assertion that the old heading "Implementation Partners" is no longer rendered
  - Add assertion that "Tech Stack" heading is rendered
  - Add assertion that the sc0red banner renders when `opportunities.length > 0`
  - Add assertion that the sc0red banner does NOT render when `opportunities` is empty (or the active-lever filter returns zero)
- [x] 5.3 Confirm coverage floor (95%) still holds

## 6. Verify

- [x] 6.1 `cd frontend && npm run lint` — no new errors
- [x] 6.2 `cd frontend && npx tsc --noEmit` — no type errors
- [x] 6.3 `cd frontend && npm test` — all tests pass
- [x] 6.4 Manual: visit an analysis page with opportunities, confirm the "Tech Stack" rename, expand/collapse the banner, click the CTA (opens new tab, lands on `sc0red.com/contact`)
- [x] 6.5 Manual: trigger a PDF export, open the PDF, confirm "Tech Stack" label and the closing sc0red block with a visible URL
- [x] 6.6 Manual: apply a lever filter that returns zero opportunities — confirm the banner is not rendered

## 7. Final copy sign-off

- [x] 7.1 Copy reviewed: no hard timeline commitment (removed "60–90 days" claim — replaced with "faster than traditional enterprise timelines"). Heading and CTA button text kept from the initial draft.

## 8. Fast-follow (descoped — tracked separately)

Section descoped from this change. The Amplify per-environment override
for `NEXT_PUBLIC_SC0RED_CONTACT_URL` was never in scope for the CTA or the
`related_services` removal. If/when a non-default contact URL is needed in
staging or production, propose a new OpenSpec change for the infra wiring.

## 9. Phase 2 — Backend removal of `related_services` (follow-up PR)

This phase is a separate PR, landing after Phase 1 (PR #178) merges. See `design.md` Decision #8 for the rationale behind the two-phase split and the full removal-touchpoint table.

### 9.1 Frontend-first removal (to close the UX regression window)

- [x] 9.1.1 Delete the "Tech Stack" section (heading + chip loop) from `frontend/src/components/OpportunitiesList.tsx`
- [x] 9.1.2 Delete the same section from `frontend/src/app/api/export/pdf/[analysisId]/route.ts` (keep the sc0red CTA block — only the per-card "Tech Stack" block goes)
- [x] 9.1.3 Drop the `related_services?: string[]` field from the `Opportunity` type in `frontend/src/lib/types/api.ts` (also removed orphan `Vendor` and `RelatedService` interfaces)
- [x] 9.1.4 Update `frontend/src/tests/components/OpportunitiesList.test.tsx` — remove the "Tech Stack" heading assertion, remove `related_services` fixture values, drop the assertion that the old "Implementation Partners" heading does not render (now trivially true)
- [x] 9.1.5 Update `frontend/src/tests/pages/AnalysisDetail.test.tsx` — remove `related_services` fixture values
- [x] 9.1.6 Grep the frontend for any remaining references to `related_services` and delete them

### 9.2 AI pipeline (prompt + schema + steps)

- [x] 9.2.1 Remove the `related_services` field from `src/pipeline/prompts/schemas/detail.json` (field definition + required array entry)
- [x] 9.2.2 Remove the "up to 3 relevant vendor / service recommendations" instruction from `src/pipeline/prompts/templates/detail.md`
- [x] 9.2.3 Remove any vendor-mention guidance from `src/pipeline/prompts/system/opportunity_detail.md`
- [x] 9.2.4 In `src/pipeline/pipeline_steps/detail_opportunity.py`, stop reading `related_services` from the model response (docstring-only change — field is no longer in schema so it's naturally absent from responses)
- [x] 9.2.5 In `src/pipeline/pipeline_steps/persist_results.py`, stop passing `related_services` when constructing `Opportunity` objects

### 9.3 Domain model

- [x] 9.3.1 Remove the `related_services: list[str] = Field(default_factory=list)` field from `Opportunity` in `src/models/model_company.py`

### 9.4 Storage (DynamoDB repository)

- [x] 9.4.1 `src/repositories/dynamodb/assessment_repository.py::save_opportunity` — stop writing `related_services` to the DynamoDB item (field no longer on model, so nothing to write)
- [x] 9.4.2 `src/repositories/dynamodb/assessment_repository.py::batch_save_opportunities` — same removal
- [x] 9.4.3 `src/repositories/dynamodb/assessment_repository.py::get_opportunities` — **went further than planned**: added active `item.pop("related_services", None)` scrub so historical rows with the stale attribute cannot leak to the API response, plus a dedicated test (`test_get_opportunities_scrubs_legacy_related_services`)
- [x] 9.4.4 No data migration — existing DynamoDB items retain the stale attribute harmlessly. Documented in PR #179 description.

### 9.5 Mock AI server

- [x] 9.5.1 Remove `related_services` from the opportunity fixtures in `scripts/mock_ai_server.py` so E2E tests exercise the post-removal shape

### 9.6 Tests (backend)

- [x] 9.6.1 Update `tests/unit/pipeline/test_detail_opportunity.py` — removed `related_services` from fixtures; added negative test `test_does_not_have_related_services`
- [x] 9.6.2 Update `tests/unit/pipeline/test_detail_opportunities.py` — fixture update
- [x] 9.6.3 Update `tests/unit/pipeline/test_generate_opportunities.py` — fixture update
- [x] 9.6.4 Update `tests/unit/repositories/test_assessment_repository.py` — removed the field from save/batch-save/get fixtures; added legacy-scrub test; split oversized file into three (`_documents.py`, `_value_chain.py`) to stay under the 400-line cap
- [x] 9.6.5 Update `tests/unit/models/test_model_company.py` — removed `related_services` fixture references (renamed `test_create_with_related_services` → `test_create_with_all_fields`)

### 9.7 Docs

- [x] 9.7.1 Remove the `related_services` row from the API contract example in `docs/api.md`

### 9.8 Verify

- [x] 9.8.1 `uv run ruff check src/` — clean
- [x] 9.8.2 `uv run pyright src/` — no new errors (pre-existing errors in unrelated files unchanged)
- [x] 9.8.3 `uv run pytest tests/ -q` — 760 passed, coverage 95.26% (≥ 95% floor; lifted from 94.98% via new `get_value_chain` tests)
- [x] 9.8.4 `cd frontend && npm run lint && ./node_modules/.bin/tsc --noEmit && npm test` — clean, 427 tests pass
- [x] 9.8.5 Ran E2E: `docker-compose.e2e.yml` + `./scripts/e2e-test.sh` — 44/44 pass. CI E2E + Playwright also green on PR #179.
- [x] 9.8.6 Architecture-reviewer agent run — no CRITICAL findings; one MEDIUM (test file size) resolved by splitting `test_assessment_repository.py` into three files.
- [x] 9.8.7 Deploy to development branch; open an existing analysis (row with stale `related_services` attribute in DynamoDB) and confirm it renders correctly (no runtime error from the now-ignored attribute) — verified post-merge (PR #179, commit 3088813)
