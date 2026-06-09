## 1. Models — explicit insufficient-data state

- [x] 1.1 Add an explicit insufficient-data state to `EbitdaTreeResult` in `model_company.py` (e.g. `grounded: bool = True` + `insufficient_data_reason: str | None = None`), additive/optional so persisted records deserialize unchanged
- [x] 1.2 Add the same insufficient-data state to `ValueChainResult`, plus a provenance field (matched template + basis) mirroring the EBITDA tree's `confidence_basis`
- [x] 1.3 Add/extend unit tests for the new model fields (defaults preserve the grounded state)

## 2. EBITDA tree — remove silent SaaS default

- [x] 2.1 In `_ebitda_templates.py`, remove `_DEFAULT_TEMPLATE_KEY` usage so `_resolve_template` reports a true no-match instead of returning the SaaS template
- [x] 2.2 In `build_ebitda_tree.py` `build_programmatic_ebitda_tree`, return the insufficient-data placeholder state on no match (and on `business_model == "unknown"`), emitting no fabricated revenue/margin/mix
- [x] 2.3 Treat a `company_size` not in `_SIZE_TO_EMPLOYEES` as a size default → `medium` confidence (unchanged), now that template is always matched for a rendered tree
- [x] 2.4 Update `_ebitda_confidence.py` so no rendered node is tagged `"low"` (dropped the `template_matched` param + dead "low" branch; return type narrowed to `high|medium`)
- [x] 2.5 Tests: unmatched model → placeholder (no SaaS numbers); `"unknown"` → placeholder; matched model → tree as before

## 3. EBITDA tree — fix range-width compounding

- [x] 3.1 In `_estimate_revenue`, replace the `emp_low×rpe_low … emp_high×rpe_high` formula with employee-band midpoint × rev-per-employee band so independent uncertainty bands are not multiplied (design Decision 3, option a)
- [x] 3.2 Test: emitted revenue range high/low ratio ≤ the larger of the two input bands' ratios (no ~13× spread)

## 4. Value chain — remove silent SaaS default + add provenance

- [x] 4.1 In `value_chain_templates.py`, remove `DEFAULT_TEMPLATE_KEY` so `_resolve_template` reports a true no-match
- [x] 4.2 In `build_value_chain.py` `build_programmatic_value_chain`, return the insufficient-data placeholder state on no match (and on `"unknown"`), emitting no fabricated steps
- [x] 4.3 Populate the value-chain `provenance_basis` (matched template + basis) on a grounded chain, consistent with EBITDA vocabulary
- [x] 4.4 Tests: unmatched/`"unknown"` model → placeholder (no SaaS steps); matched model → chain + provenance

## 5. Profile extraction — ground the facts

- [x] 5.1 Update `prompts/schemas/profile.json`: fix `company_size` enum to the size-map keys + `"unknown"`; instruct `"unknown"` for ungroundable `business_model` / `revenue_model`
- [x] 5.2 Update `prompts/system/profile_extraction.md`: instruct that existing-fact fields must be supported by scraped content; return `"unknown"` when unsupported rather than guessing
- [x] 5.3 Tests for the schema/grounding contract: `company_size` enum aligns with the size map; `"unknown"` business model flows to placeholders downstream

## 6. Frontend — render the placeholder state + clickable upload CTA

- [x] 6.1 Branch the EBITDA/financial report section on the insufficient-data flag → render the labeled placeholder (`InsufficientDataPlaceholder`, design Decision 7 copy)
- [x] 6.2 Branch the value-chain report section on the insufficient-data flag → render the placeholder
- [x] 6.3 Profile FACT fields that are `"unknown"` — verified they are NOT surfaced to any frontend/PDF surface (only internal pipeline inputs + the empty `businessModelSummary`, which the placeholder replaces), so the literal sentinel never reaches the UI. No render change needed.
- [x] 6.4 Make the placeholder CTA a clickable control that scrolls to the always-present `#document-upload` widget (existing `DocumentUpload` + `useReanalyze` + `ReanalyzeProgressCard`) — no new feature
- [x] 6.5 CTA target is the unconditionally-rendered document-upload section, so it is never a dead-end link — no separate uploads-enabled flag needed (the upload widget itself handles the `501 NOT_CONFIGURED` state). Deviation from the original gating plan, documented here.
- [x] 6.6 Vitest + RTL tests: placeholder render per section (EBITDA + value chain + standalone component); CTA click scrolls to upload; grounded data renders the real tree/diagram; legacy (no flag) treated as grounded
- [x] 6.7 (added) PDF/print path: `PrintEbitdaOutline` + `PrintReport` render the placeholder when ungrounded (the customer's artifact was a PDF) + tests

## 7. Durability — audit rule

- [x] 7.1 Add a `make audit` check — forward invariant: every `build_programmatic_*` fact-bearing builder MUST carry an insufficient-data (`grounded=False`) branch (can't be bypassed by renaming the default constant)
- [x] 7.2 Test the audit rule fires on a builder missing the branch (incl. a renamed-constant bypass attempt) and passes on the fixed builders

## 8. Validation & verification

- [x] 8.1 `ruff check` + `ruff format` clean on changed files; naming validator exits 0 (no new blocking violations)
- [x] 8.2 `pyright src/` introduces no new error category (the +2 are the file's pre-existing `company`-possibly-None false-positive pattern in `tools_read.py`)
- [x] 8.3 `pytest tests/ -q` passes (1263) with coverage 95.67% ≥ 95%
- [x] 8.4 Frontend `tsc --noEmit` clean, lint clean, `vitest run` passes (1165)
- [x] 8.5 Ran the `architecture-reviewer` agent — 0 CRITICAL; the 1 MEDIUM (MCP read tools) + 3 LOW findings all resolved
- [x] 8.6 Customer case covered at the builder level: `test_debt_settlement_renders_placeholder_not_saas` (EBITDA) + `test_debt_settlement_renders_placeholder` (value chain) — both confirm placeholder, no SaaS fabrication
- [x] 8.7 Ran the E2E suite per CLAUDE.md — 45/45 passed (mock returns a SaaS/matched model, so the grounded happy path is unchanged)
