## 1. Backend model + schema

- [x] 1.1 In `backend/src/models/model_company.py`, add `confidence_level: Literal["high", "medium", "low"] | None = None` and `confidence_basis: str | None = None` to `EbitdaNode`. Use `from typing import Literal` if not already imported. — Also added a class docstring explaining the provenance contract.
- [x] 1.2 Verify `EbitdaTreeResult` round-trips through Pydantic with old payloads (no fields) — add a regression test that loads a fixture stored before this change and asserts no `ValidationError` is raised. — `TestEbitdaNodeBackwardCompat` covers both single-node and full-tree round-trips.
- [x] 1.3 Update the JSON schema mirror used by external consumers (if one is checked in under `backend/src/pipeline/prompts/schemas/` or similar) to add the two new optional fields. If no such mirror exists for `EbitdaNode`, skip. — No mirror exists; the EBITDA tree is built programmatically (no AI call), so there's no prompt schema to update. Skipped.

## 2. Backend pipeline — provenance tagging

- [x] 2.1 In `backend/src/pipeline/pipeline_steps/build_ebitda_tree.py`, define the three confidence-decision branches as named helper functions (or inline if cleaner): `_confidence_for_revenue_node`, `_confidence_for_cost_node`. Each takes the inputs that drove the node and returns a `(level, basis)` tuple. — Implemented as a single `_compute_confidence(node_kind="revenue"|"cost")` helper that handles both via a parameter — same shape, less duplication. `_resolve_template` and `_estimate_revenue` were extended to also return whether the input matched (booleans flow into `_compute_confidence`).
- [x] 2.2 Wire `confidence_level` and `confidence_basis` into every leaf-node construction site in `build_programmatic_ebitda_tree`. Rollup/subtotal nodes set both to `None` per the spec. — Revenue/COGS/OpEx parents AND their children carry confidence; gross_profit and ebitda subtotals do not.
- [x] 2.3 Confidence rules must match the spec exactly:
  - **high** when `business_model` resolves to a known `_MODEL_KEYWORDS` entry AND `company_size` is a key in `_SIZE_TO_EMPLOYEES`
  - **medium** when exactly one of (template, size) resolves; the other defaulted to `_DEFAULT_TEMPLATE_KEY` (saas) or `_DEFAULT_EMPLOYEES`
  - **low** when both defaulted — neither input gave a usable signal

## 3. Backend tests

- [x] 3.1 In `backend/tests/unit/pipeline/test_build_ebitda_tree.py`, add tests for each confidence branch: high (both `business_model` and `company_size` resolve), medium (exactly one resolves — both directions: known model + unknown size, and unknown model + known size), low (both defaulted). Use representative `CompanyProfile` fixtures. — `TestConfidenceComputation` covers all four cells of the (template_matched × size_matched) matrix plus inheritance tests.
- [x] 3.2 Test that subtotal/margin nodes have `confidence_level is None`. — `test_subtotal_and_margin_nodes_carry_no_confidence`.
- [x] 3.3 Test the human-readable basis strings — assert they reference the resolved/defaulted inputs (e.g., a high-confidence basis mentions both the matched template and the matched size; a medium basis names which side defaulted; a low basis indicates both fell back). Use substring asserts to keep the tests resilient to copy edits. — Substring asserts on "matched" / "default" / template label / size bracket name / "industry-benchmark" for cost basis.
- [x] 3.4 Run `cd backend && uv run pytest tests/ -q` — all green; coverage ≥ 95%. — 996 passed, coverage 95.07%.
- [x] 3.5 Run `cd backend && uv run ruff check src/` — clean.
- [x] 3.6 Run `cd backend && uv run pyright src/` — no new errors vs baseline. — 401 errors at baseline; 401 with these changes (zero new).

## 4. MCP smoke test for additive schema

- [x] 4.1 If the MCP server (`openspec/specs/mcp-repository-access/spec.md`) exposes the EBITDA tree, add a smoke test that the new fields don't break existing tool calls. Old records (without the fields) and new records (with them) both serialize through the MCP boundary. — `test_tree_with_confidence_fields_does_not_break_tool` covers the new fields; `test_returns` already covered the old shape.

## 5. Frontend types + component

- [ ] 5.1 In `frontend/src/lib/types/api.ts`, extend the `EbitdaNode` (or equivalent) type with `confidenceLevel?: "high" | "medium" | "low"` and `confidenceBasis?: string`. Keep the camelCase ↔ snake_case mapping consistent with the rest of the file.
- [ ] 5.2 In `frontend/src/components/EbitdaNodeComponent.tsx`, render a `ConfidenceIndicator` next to `value_range` when `confidenceLevel` is non-null. Map `high → 3`, `medium → 2`, `low → 1` dots.
- [ ] 5.3 Wrap the chip in a `HelpTooltip` (or its equivalent primitive) that displays `confidenceBasis`. If `HelpTooltip` does not yet support a free-form `content` prop (today it takes a registry `term` key), add the additive prop variant — small refactor, no breaking change.
- [ ] 5.4 Suppress the chip and tooltip entirely when `confidenceLevel` is `null` or `undefined`. No "unknown" badge.

## 6. Frontend legend

- [ ] 6.1 Add a small legend block to `frontend/src/components/EbitdaTree.tsx` near the tree (above or in a collapsed disclosure) explaining: high = anchored to declared data; medium = inferred from company size + industry benchmark; low = defaulted from a size bracket. Plain copy, no jargon.
- [ ] 6.2 Visual polish: legend uses the existing typography and spacing tokens — does not introduce new design primitives.

## 7. Print export

- [ ] 7.1 In `frontend/src/components/print/PrintEbitdaOutline.tsx`, render the confidence level inline as `(high)` / `(medium)` / `(low)` after the value range when `confidenceLevel` is non-null. No marker when null.
- [ ] 7.2 Decide whether to render `confidenceBasis` inline as italic small text in print, or to omit it. Default: omit (concise PDFs read better); resolve in code review.

## 8. Frontend tests

- [ ] 8.1 In `frontend/src/tests/components/EbitdaTree.test.tsx` (or extract to a focused `EbitdaNodeComponent.test.tsx`), add tests:
  - High-confidence node renders 3-dot chip
  - Medium → 2 dots, Low → 1 dot
  - Null confidence renders no chip, no fallback badge
  - Subtotal / margin nodes render no chip
- [ ] 8.2 Tooltip a11y tests:
  - Tab focuses the chip
  - Enter/Space reveals the tooltip with `confidenceBasis` text
  - Pointer hover reveals the tooltip after the same delay as other `HelpTooltip` instances
  - Touch-tap toggles the tooltip; tapping outside dismisses
- [ ] 8.3 Update `frontend/src/tests/components/print/PrintEbitdaOutline.test.tsx` to assert the inline confidence marker renders for non-null and is absent for null.
- [ ] 8.4 Run `cd frontend && npm run lint && npx tsc --noEmit && npm test` — all clean.

## 9. Quality gates + rollout

- [ ] 9.1 Architecture-reviewer agent run on the combined backend + frontend diff. Resolve all CRITICAL + MEDIUM findings.
- [ ] 9.2 E2E suite (`E2E_MODE=full`) — no regressions. New E2E test for "EBITDA tree renders confidence chip on freshly-analysed company."
- [ ] 9.3 Playwright visual regression captures the EBITDA section with confidence chips at desktop + mobile viewports.
- [ ] 9.4 PR per layer (backend, frontend, print). Backend ships first; frontend gracefully degrades when fields are absent. Each PR self-contained.
- [ ] 9.5 No infrastructure changes — verify CDK synth on backend PR shows no diff.
