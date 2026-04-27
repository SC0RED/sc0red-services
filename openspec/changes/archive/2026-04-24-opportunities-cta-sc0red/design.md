## Context

Current rendering in `OpportunitiesList.tsx` (lines 319-347) and the PDF export route:

```
Opportunity card (expanded)
├─ Description
├─ Implementation Steps (numbered)
├─ [Investment] [ROI]  (two-column grid)
└─ "Implementation Partners" row
    └─ badge badge-neutral × N  ← neutral gray pills
```

Same block exists in `frontend/src/app/api/export/pdf/[analysisId]/route.ts` (lines 145-152) with `.vendor-chip` styling.

The `related_services` field comes from the backend pipeline (`detail.json` schema: "Up to 3 relevant vendor or service names"). It is produced by the `DetailOpportunity` step, persisted into DynamoDB via `assessment_repository.py`, and returned from the API as `Opportunity.related_services`. Phase 1 of this change leaves the data untouched and is purely presentational; Phase 2 removes the field end-to-end.

## Goals / Non-Goals

**Goals:**
- Reposition sc0red as *the* implementation partner, not one of many
- Place the sc0red pitch at the point of maximum reader interest — after they've read the opportunities, before they close the tab
- Keep the pitch discoverable but not noisy (a single placement, not per-card)
- Mirror the treatment in the PDF export so printed artifacts carry the same framing
- Keep the contact URL easy to rotate (env-configurable)
- **Phase 2:** remove the `related_services` field end-to-end once the Phase 1 reposition has shipped, eliminating the AI token / storage / bandwidth cost of a field we've de-emphasized

**Non-Goals:**
- Click analytics (separate proposal)
- Per-opportunity CTA (explicitly rejected — too noisy)
- Redesigning the opportunity cards themselves
- **Phase 1 only:** modifying backend pipeline output, schemas, or the stored field (deferred to Phase 2)

## Decisions

### 1. Bottom placement, not top

**Decision: The sc0red banner sits at the **bottom** of the opportunities list, after the last opportunity card.**

Top placement (before the cards) pitches before the reader has built up interest — the CTA lands cold. Bottom placement follows the natural reading arc:

```
What opportunities exist?  →  What does each one cost/return?  →  WHO BUILDS THIS?
      (the cards)                  (per-card detail)               (sc0red banner)
```

By the time the reader reaches the banner, they've seen every opportunity. They've either been convinced or they haven't — either way, the CTA lands with full context.

### 2. Single banner, not per-card

**Decision: One CTA at the bottom of the list, not a hook on each card.**

We considered a per-card "sc0red implements this →" line in the collapsed header (always visible, maximum touchpoints). Rejected because:

- A scan with 15 opportunities would show 15 CTAs on screen at once — reads as spam
- Each per-card CTA would need its own copy variant to feel varied, or identical copy that reads repetitive
- The CTA has nothing opportunity-specific to say beyond "we build this" — the sc0red value prop is holistic, not per-opportunity

A single well-placed banner carries more weight than 15 muted ones.

### 3. Expandable, collapsed by default

**Decision: The banner renders collapsed by default, with a chevron to expand into the full pitch.**

```
Collapsed (default):
┌──────────────────────────────────────────────────────────┐
│  ◆  sc0red can help you capture these opportunities   ▾ │
└──────────────────────────────────────────────────────────┘

Expanded:
┌──────────────────────────────────────────────────────────┐
│  ◆  sc0red can help you capture these opportunities   ▴ │
│                                                          │
│  Our AI specialists implement opportunities like these   │
│  from strategy through production deployment —           │
│  typically in 60–90 days.                                │
│                                                          │
│  [  Start the conversation →  ]                          │
└──────────────────────────────────────────────────────────┘
```

Rationale:
- Collapsed-by-default keeps the page visually clean and doesn't make the banner feel salesy
- The single collapsed line is enough to plant the association ("sc0red = can help with this") for readers who don't expand
- Readers who engage get a fuller pitch + a clear next step

Accessibility: follows the same `aria-expanded` + `aria-controls` pattern the opportunity cards already use.

### 4. Tech Stack relabel (Phase 1 interim), vendor chips retained for now

**Decision: Phase 1 renames the per-card "Implementation Partners" section to "Tech Stack" and keeps the vendor chips as-is. Phase 2 removes the section and the underlying field entirely.**

The vendor names (Datadog, Salesforce, Veeva, etc.) are useful context — they signal technical realism. But labeled "Implementation Partners" they imply those vendors do the implementing. Under "Tech Stack" they read as "the tools a real build would touch" — credibility without competing with sc0red for the partner framing.

In Phase 1, no visual changes to the chips themselves. Only the heading text changes, in both the React component and the PDF export.

**Why not remove in Phase 1?** Removing the section in the same PR as adding the CTA means shipping two messages at once (pull a thing out, push a new thing in). Renaming first keeps the in-flight PR focused on the reposition and gives us a quick escape hatch if we find we do want a vendor context signal long-term. Phase 2 commits to full removal once the CTA has lived in production.

### 5. Env-configurable CTA URL

**Decision: Read the contact URL from `NEXT_PUBLIC_SC0RED_CONTACT_URL`, default to `https://www.sc0red.com/contact`.**

- `NEXT_PUBLIC_*` makes it available in client-side code (the banner is a client component)
- Default constant means no deploy-time configuration is required for it to work
- Trivial to swap to a Calendly link, a different domain, or an internal routing URL later by setting the env var

**Scope note:** This PR wires the resolver at the Next.js code level only. Per-environment override at the CDK / Amplify branch level (so staging can point elsewhere than production) is a fast-follow task. The Amplify build spec already greps for `NEXT_PUBLIC_*` into `.env.production`, but `amplify_construct.py::create_branch()` does not currently inject this variable — so the default is used for all deployed builds today. That's fine: the default IS the production URL. Only when we want to diverge per environment do we need the CDK wiring.

### 6. PDF export: static, non-interactive, same messaging

**Decision: The PDF renders the expanded state inline (no collapse), with the same copy and the contact URL printed as a visible link.**

Rationale:
- PDFs are artifacts people share inside a firm — the printed CTA should stand on its own without requiring a click
- Printing a "[Learn more ▾]" affordance in a PDF would be confusing (no click in print)
- The URL should be visible text, not a hidden `href`, so recipients of a printed copy can type it

Per-card vendor chips keep their existing `.vendor-chip` styling, only the heading text changes to "Tech Stack".

### 7. Banner visibility tied to `filteredOpps.length > 0`

**Decision: The banner only renders when at least one opportunity is visible in the current filter.**

If the user filters to a lever (Revenue / Cost / Both) and the filter returns zero results, we don't show a sc0red CTA pitching about "these opportunities" when there aren't any. The component already tracks `filteredOpps` — gate on that.

### 8. Phase 2 — full backend removal of `related_services`

**Decision: Ship the field removal as a follow-up PR after Phase 1 merges, not as part of the same change.**

The original intent was to *replace* third-party implementation-partner framing with sc0red branding. Phase 1 repositions; Phase 2 removes the competing signal at the source. Leaving `related_services` in the backend indefinitely is waste on three axes:

- **AI tokens.** The prompt instructs the model to produce "up to 3 vendor recommendations per opportunity." At ~10-30 tokens per opportunity × 8-15 opportunities per scan, that's ~50-100 tokens per scan on a field we now hide.
- **Storage / bandwidth.** Each opportunity carries 0-3 vendor strings through DynamoDB writes, API responses, and SSR payloads.
- **Cognitive surface.** Every engineer reading the model, the repository, or the types sees a field they must reason about ("is this still used? why?").

**Why two phases and not one?**

- The Phase 1 PR is already in flight (PR #178). Expanding its scope into a pipeline-schema change, prompt-template edit, Pydantic-model change, repository-method change, and coordinated test updates across backend + frontend triples the review surface and blocks the reposition on a larger change.
- Phase 2 is a pure-delete PR (no new behavior, only removal). Shipping it standalone gives a clean diff and a clean revert path if we find downstream consumers we missed.
- **Data migration is unnecessary.** DynamoDB attributes are per-item and the read path ignores attributes it doesn't deserialize. Existing rows with `related_services` stored continue to work — the attribute is simply no longer read. Over time, writes without the attribute dominate the dataset.

**Phase 2 scope (removal touchpoints):**

| Layer | File | Change |
|-------|------|--------|
| AI schema | `src/pipeline/prompts/schemas/detail.json` | Remove `related_services` field and its schema entry |
| Prompt template | `src/pipeline/prompts/templates/detail.md` | Remove the "up to 3 vendor recommendations" instruction |
| System prompt | `src/pipeline/prompts/system/opportunity_detail.md` | Remove vendor-mention guidance |
| Pipeline step | `src/pipeline/pipeline_steps/detail_opportunity.py` | Stop extracting `related_services` from model output |
| Pipeline step | `src/pipeline/pipeline_steps/persist_results.py` | Stop passing `related_services` when constructing `Opportunity` |
| Domain model | `src/models/model_company.py` | Remove the `related_services` field on `Opportunity` |
| Storage (write) | `src/repositories/dynamodb/assessment_repository.py::save_opportunity` | Stop writing the attribute |
| Storage (batch write) | `src/repositories/dynamodb/assessment_repository.py::batch_save_opportunities` | Stop writing the attribute |
| Storage (read) | `src/repositories/dynamodb/assessment_repository.py::get_opportunities` | Stop deserializing the attribute (reads ignore it) |
| Mock AI | `scripts/mock_ai_server.py` | Remove from fake responses so E2E doesn't simulate a dead field |
| Frontend type | `frontend/src/lib/types/api.ts` | Remove `related_services?: string[]` from `Opportunity` |
| Frontend UI | `frontend/src/components/OpportunitiesList.tsx` | Delete the entire "Tech Stack" section (heading + chips) |
| Frontend PDF | `frontend/src/app/api/export/pdf/[analysisId]/route.ts` | Delete the "Tech Stack" section |
| Frontend tests | `OpportunitiesList.test.tsx`, `AnalysisDetail.test.tsx`, others | Remove fixtures / assertions referencing `related_services` |
| Backend tests | `test_detail_opportunity.py`, `test_generate_opportunities.py`, `test_assessment_repository.py`, `test_model_company.py` | Remove fixtures / assertions |
| Docs | `docs/api.md` | Remove field from the API contract table |

**Expected wins:**
- ~50-100 tokens saved per scan (AI cost)
- Smaller DynamoDB items, smaller API responses, smaller SSR payloads
- One fewer field to maintain in the AI schema, domain model, repository, types, and docs
- Frontend leads with the sc0red CTA without a competing "vendor chip" signal

## Risks / Trade-offs

- **Copy tone.** The recommended copy ("sc0red delivers this. Our AI specialists implement opportunities like this from strategy through production — typically in 60–90 days.") makes a specific time claim. If 60–90 days isn't a commitment we can make, soften to "in a matter of weeks" or drop the timeline. The proposal ships with conservative copy; a final copy review with whoever owns marketing is a task item.
- **Env var fallback silently hides misconfiguration.** If `NEXT_PUBLIC_SC0RED_CONTACT_URL` is set to an empty string, the banner's link would be a broken `href=""`. Mitigation: the component treats any falsy env value as "use default" rather than honoring an empty string. Documented in `.env.local.example`.
- **PDF inline URL readability.** Rendering a full URL as visible text (`https://www.sc0red.com/contact`) can look ugly in a printed doc. Mitigation: print it on its own line in a subdued color, not inline with pitch copy.
- **Future per-card variant.** If we ever want per-card CTAs (e.g., "request sc0red to spec this one opportunity"), the banner-only shape here doesn't block it — it just chooses not to go there today. Future work can add per-card hooks without reshaping the banner.
- **Phase 2: coupled frontend + backend PR.** Phase 2 deletes a field consumed by both the frontend and the backend. The PR must update the Pydantic model, the repository, the pipeline step output, the prompt, the mock AI server, the frontend type, and the UI in lockstep — if the frontend ships first without the backend cleanup, the deployed app still shows an empty "Tech Stack" section for existing analyses. Mitigation: in Phase 2, remove the frontend Tech Stack block first (or together) so the UI no longer cares whether the field is present. Backend change can then land at leisure without a UX regression window.
- **Phase 2: historical DynamoDB rows retain the attribute.** This is intentional — DynamoDB has no schema enforcement, so leaving stale attributes on old rows is free. Reads simply ignore them. If we later decide we want a clean dataset, a one-shot `UPDATE` pass over the table is trivial; it's not blocking.
- **Phase 2: prompt-change may perturb opportunity output.** Removing "also list up to 3 vendors" from the prompt is a surface-level change, but any prompt edit risks secondary drift in what the model produces for other fields. Mitigation: the existing E2E suite scans a known fixture — run it before and after the prompt edit and compare `Opportunity.description` / `implementation_steps` for regressions.
