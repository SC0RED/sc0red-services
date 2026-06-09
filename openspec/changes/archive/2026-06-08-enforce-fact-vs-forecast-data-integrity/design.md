## Context

The report is assembled from two kinds of content:

- **FACT** surfaces — what the company *is* today: the company profile (industry, business model, size, revenue model), the EBITDA/financial tree, and the value chain (how they operate). These are read by the customer as statements about their own business.
- **FORECAST** surfaces — what they *could* do: risk scores, opportunities/value levers, the strategy map.

Two FACT surfaces are built deterministically from hardcoded industry templates keyed off the AI-extracted `business_model` string:

- `build_programmatic_ebitda_tree` (`build_ebitda_tree.py` + `_ebitda_templates.py` + `_ebitda_confidence.py`)
- `build_programmatic_value_chain` (`build_value_chain.py` + `value_chain_templates.py`)

Both resolve the template via keyword match and, on no match, **silently fall back to `"saas"`** (`_DEFAULT_TEMPLATE_KEY` / `DEFAULT_TEMPLATE_KEY`). For a debt-settlement company this produced a confident, fully-fabricated SaaS P&L and SaaS operating model — the customer-reported defect. The EBITDA tree has a deterministic confidence label (`ebitda-tree-confidence` spec) that *detects* the fallback but still emits the SaaS numbers; the value chain has no confidence signal at all.

A second defect: `_estimate_revenue` computes `low = employee_low × rev_per_emp_low` and `high = employee_high × rev_per_emp_high`, compounding two independent uncertainty bands into a ~13× range ($30M–$400M) shown as a definite figure — wrong even when the template *does* match.

A third: the profile schema instructs the AI to emit `company_size: "Enterprise 1000+"`, which is not a key in `_SIZE_TO_EMPLOYEES` (`"Large 1000-5000"` / `"Enterprise 5000+"`), so size silently defaults too. Profile facts are not required to be grounded in the scraped text.

Constraints (CLAUDE.md): pipeline work stays in `RequestStep` subclasses wired through the factory chain; prompts live in `src/pipeline/prompts/`; strict fail-fast — no silent fallbacks on required fields; Python files < 400 lines; 95% coverage; feature branch → PR (never commit to `development`).

## Goals / Non-Goals

**Goals:**
- The report never asserts an existing FACT it cannot ground. Ungroundable FACT surfaces render an explicit "insufficient public data to model this" placeholder.
- Remove the silent SaaS default from both the EBITDA tree and the value chain.
- The EBITDA range, when a template matches, is not a misleadingly-wide compounded band.
- The value chain carries a derivation-provenance signal equivalent to the EBITDA tree's.
- Profile facts (`business_model`, `revenue_model`, `company_size`) are grounded in scraped content or marked low-confidence/omitted; `company_size` values align with the size map.
- A `make audit` rule prevents reintroducing a silent default on a fact-bearing section.

**Non-Goals:**
- "Forecast framing" — rewording opportunities / value levers / strategy map as explicit suggestions. Deferred (see Open Questions / next step).
- Adding new industry templates (debt settlement, collections, etc.). The fix is to *fail honestly* on no-match, not to chase template coverage (whack-a-mole). New templates can be added later behind the same grounded contract.
- Sourcing real third-party financial data (e.g. paid data providers). Out of scope.
- DynamoDB schema migration — all new fields are additive/optional.

## Decisions

### Decision 1: No-match → explicit placeholder, not silent SaaS, not silent omission

`_resolve_template` currently returns `(template, matched: bool)` for EBITDA and `(key, steps)` for the value chain. On no match we will **not** substitute a default template. Instead the builder returns a result in an "insufficient data" state that the model and frontend render as a labeled placeholder ("We don't have enough public data to model this company's [financials / operating model] with confidence").

- **Why placeholder over silent suppression:** matches the repo's fail-fast/visible-state culture; an empty gap reads as a rendering bug, while a labeled placeholder reads as honesty and preserves trust.
- **Why placeholder over keep-the-SaaS-guess-with-a-low-confidence-chip:** the customer feedback proves a low-confidence chip does not undo a confidently-worded wrong sentence. A FACT we can't ground must not be stated at all.
- **Alternative considered — fall back to a generic, model-agnostic template** (no revenue mix, just "revenue/costs unknown"): rejected because any concrete number is still a fabricated fact; the placeholder is the honest representation.

### Decision 2: Represent the placeholder as an explicit state on the result models

Add an explicit insufficient-data flag + reason to `EbitdaTreeResult` and `ValueChainResult` (e.g. `grounded: bool` / `insufficient_data_reason: str | None`, or a small status enum) rather than overloading "empty nodes list". Builders return this state on no-match; the API serializes it; the frontend branches on it. Keeping it an explicit field (not an inferred emptiness) satisfies fail-fast and is unambiguous for the audit rule and tests.

### Decision 3: EBITDA range — stop compounding independent bands

Replace the `low = emp_low × rev_per_emp_low`, `high = emp_high × rev_per_emp_high` formula with one that does not multiply the two band extremes against each other. Options to settle in implementation: (a) use a single representative employee count (band midpoint) × the rev-per-employee band, so only one dimension of uncertainty drives the range; (b) keep both but narrow via geometric/representative combination. The spec requirement is behavioral: the emitted high/low ratio must not exceed the larger of the two input bands' own ratios (i.e. uncertainty is not multiplied). This keeps the figure honest as a FACT-with-confidence rather than a uselessly wide guess.

### Decision 4: Value-chain provenance mirrors EBITDA, reusing the matched signal

The value chain already computes `template_key` via the same keyword match. Surface the same matched/defaulted signal as a provenance field on `ValueChainResult` (and/or per `ValueChainStep`), reusing the EBITDA confidence vocabulary so the two FACT surfaces are consistent. Since no-match now yields the placeholder (Decision 1), the provenance signal on a *rendered* value chain is always "matched"; the field still records the basis for audit/debug parity with EBITDA.

### Decision 5: Profile grounding via prompt + schema, not a new pipeline step

Profile extraction is already an AI call reading scraped text. Tighten it at the prompt/schema layer rather than adding a verification step:
- `profile_extraction.md` (system prompt): instruct that existing-fact fields MUST be supported by the scraped content; when the site gives no signal for a field, return a sentinel (e.g. `"unknown"`) rather than guessing.
- `profile.json` (schema): fix `company_size` enum to the size-map keys (`Startup <50`, `Small 50-200`, `Mid-market 200-1000`, `Large 1000-5000`, `Enterprise 5000+`) so a valid extraction can never silently default; allow the `"unknown"` sentinel for ungroundable fact fields.
- Downstream builders treat `"unknown"` business model / size as a no-match → placeholder (Decision 1), closing the loop.

This avoids an extra AI round-trip and keeps prompt text externalized per CLAUDE.md.

### Decision 6: Audit rule for silent defaults on fact-bearing sections

Add a check to the audit script (`make audit`) that flags a module-level `DEFAULT_*TEMPLATE_KEY` (or equivalent default-template constant) used by a fact-bearing builder without an accompanying explicit insufficient-data path. Concretely: grep for default-template constants in `pipeline_steps` and assert the builder has a no-match placeholder branch. This is a guardrail, not a proof — its job is to make the next person who adds a fact section think about grounding.

## Risks / Trade-offs

- **[Placeholder appears more often than expected — many real companies match no template]** → Mitigation: the keyword buckets are broad (saas/services/ecommerce/manufacturing/financial_services); measure no-match rate after deploy. If high, add templates *behind the grounded contract* (still honest, just more coverage). Placeholder-too-often is a quality signal, not a correctness bug.
- **[Frontend shows a gap if it doesn't handle the new state]** → Mitigation: the explicit model field (Decision 2) forces a branch; add a frontend test for the placeholder state per CLAUDE.md test standards.
- **[Range formula change shifts numbers for already-matched companies]** → Mitigation: this is intended (narrower, honest ranges); cover with tests asserting the ratio bound; note it as a visible report change.
- **[`"unknown"` sentinel leaks into customer-visible profile text]** → Mitigation: profile FACT fields rendering `"unknown"` should be omitted/placeholdered on the frontend, same contract as the tree.
- **[Audit rule is heuristic and could be bypassed]** → Accepted: it raises the floor; the spec + review gate are the real enforcement.

## Migration Plan

1. Additive model fields (default to the grounded/matched state) — no data migration; existing persisted records deserialize unchanged.
2. Ship backend builders + profile prompt/schema together so a `"unknown"`/no-match flows end-to-end to the placeholder.
3. Frontend handles the placeholder state in the same release.
4. Rollback: revert the branch; old records remain valid because new fields are optional.

### Decision 7: Placeholder copy and a clickable "attach a document" CTA

Placeholder copy is locked (principled voice — we only present facts we can ground). Each placeholder ends with an actionable CTA **that is a clickable control, not static text**: it opens the existing `DocumentUpload` flow and, on a successful upload, kicks the existing re-analyse flow (`POST /api/analysis/{analysis_id}/reanalyze`). No new feature is built — the CTA wires into `DocumentUpload.tsx` + the `reanalyze` route + `ReanalyzeProgressCard` that already exist.

The CTA renders **conditionally** — only when document uploads are enabled. `handle_upload_url` returns `501 NOT_CONFIGURED` when S3 isn't set up, so the placeholder component needs an "uploads enabled" signal (a capability flag from the API, or derived from upload availability) to avoid showing a dead-end link. When uploads are disabled, only the principled body renders, without the CTA.

Final copy:

- **Financial / EBITDA** — heading: "Financial model not shown". Body: "We couldn't establish this company's revenue model from public information, so we've left the financial breakdown out rather than estimate one. sc0red Services only presents financials it can ground in evidence." CTA (if uploads enabled, clickable): "Have internal financials? Attach a document and we'll re-analyse."
- **Value chain / operating model** — heading: "Operating model not shown". Body: "We couldn't determine how this business operates from available public sources, so we haven't mapped a value chain. sc0red Services maps operations only when the underlying model is clear." CTA (if uploads enabled, clickable): "Attach a document describing the business and we'll re-analyse."
- **Profile `"unknown"` fields (inline):** "Not determined from public sources" (omit the literal `"unknown"`; no CTA at field level).

## Open Questions

- Range formula choice (Decision 3 option a vs. b) — settle during implementation against real examples; the spec bound is the contract.
- Re-analyse trigger UX after upload — auto-kick on successful upload vs. an explicit "Re-analyse now" confirm. Lean toward reusing whatever `DocumentUpload` + `ReanalyzeProgressCard` already do today; confirm during implementation.

## Documented Next Step (out of scope here)

**Forecast framing.** The forward-looking surfaces (opportunities, value levers, strategy map) should be reworded so they read as explicit suggestions ("we'd explore…", "a potential lever…") rather than statements of fact, so a reader never mistakes a forecast for a measurement. The user wants to explore this separately. Captured here so the context is not lost; it is intentionally **not** implemented in this change.
