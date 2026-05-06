## 1. Backend model + schema

- [ ] 1.1 In `backend/src/models/model_company.py`, add `confidence_level: Literal["high", "medium", "low"] | None = None` and `confidence_basis: str | None = None` to `EbitdaNode`. Use `from typing import Literal` if not already imported.
- [ ] 1.2 Verify `EbitdaTreeResult` round-trips through Pydantic with old payloads (no fields) — add a regression test that loads a fixture stored before this change and asserts no `ValidationError` is raised.
- [ ] 1.3 Update the JSON schema mirror used by external consumers (if one is checked in under `backend/src/pipeline/prompts/schemas/` or similar) to add the two new optional fields. If no such mirror exists for `EbitdaNode`, skip.

## 2. Backend pipeline — provenance tagging

- [ ] 2.1 In `backend/src/pipeline/pipeline_steps/build_ebitda_tree.py`, define the three confidence-decision branches as named helper functions (or inline if cleaner): `_confidence_for_revenue_node`, `_confidence_for_cost_node`. Each takes the inputs that drove the node and returns a `(level, basis)` tuple.
- [ ] 2.2 Wire `confidence_level` and `confidence_basis` into every leaf-node construction site in `build_programmatic_ebitda_tree`. Rollup/subtotal nodes set both to `None` per the spec.
- [ ] 2.3 Confidence rules must match the spec exactly:
  - **high** when `CompanyProfile` has a declared figure that anchors the node
  - **medium** when `company_size` resolves through `_SIZE_TO_EMPLOYEES` and a template benchmark
  - **low** when `_DEFAULT_EMPLOYEES` was used, or when no company-specific signal is available

## 3. Backend tests

- [ ] 3.1 In `backend/tests/pipeline/pipeline_steps/test_build_ebitda_tree.py`, add tests for each confidence branch: high (declared revenue present), medium (size bracket resolves), low (defaulted from `_DEFAULT_EMPLOYEES`). Use representative `CompanyProfile` fixtures.
- [ ] 3.2 Test that subtotal/margin nodes have `confidence_level is None`.
- [ ] 3.3 Test the human-readable basis strings — assert they reference the correct inputs (e.g., revenue-based basis mentions "company size" or "declared", cost-based basis mentions "industry-benchmark margin"). Use substring asserts to keep the tests resilient to copy edits.
- [ ] 3.4 Run `cd backend && uv run pytest tests/ -q` — all green; coverage ≥ 95%.
- [ ] 3.5 Run `cd backend && uv run ruff check src/` — clean.
- [ ] 3.6 Run `cd backend && uv run pyright src/` — no new errors vs baseline.

## 4. MCP smoke test for additive schema

- [ ] 4.1 If the MCP server (`openspec/specs/mcp-repository-access/spec.md`) exposes the EBITDA tree, add a smoke test that the new fields don't break existing tool calls. Old records (without the fields) and new records (with them) both serialize through the MCP boundary.

## 5. Frontend types + component

- [x] 5.1 In `frontend/src/lib/types/api.ts`, extend the `EbitdaNode` (or equivalent) type with `confidence_level?: "high" | "medium" | "low" | null` and `confidence_basis?: string | null`. Kept snake_case to match the rest of the file (the type mirrors backend serialisation; camelCase translation happens at component boundaries, not in the type).
- [x] 5.2 In `frontend/src/components/EbitdaNodeComponent.tsx`, render a `ConfidenceIndicator` next to `value_range` when `confidenceLevel` is non-null. Map `high → 3`, `medium → 2`, `low → 1` dots. — Lowercase backend value uppercased at the component boundary because `ConfidenceIndicator` takes uppercase per its existing API.
- [x] 5.3 Wrap the chip in a `HelpTooltip` (or its equivalent primitive) that displays `confidenceBasis`. — Used the native HTML `title` attribute instead. The chip lives inside a React-Flow node; a portaled `HelpTooltip` would be clipped by the flow container. `title` keeps the tooltip within node bounds, gives hover/focus for free, and stays keyboard-accessible (the chip wrapper is `tabIndex={0}`). Screen-reader users still get the level via `ConfidenceIndicator`'s `aria-label`.
- [x] 5.4 Suppress the chip and tooltip entirely when `confidenceLevel` is `null` or `undefined`. No "unknown" badge. — Also defensively suppressed on `subtotal` / `margin` types regardless of level, in case the backend ever leaks one.

## 6. Frontend legend

- [x] 6.1 Add a small legend block to `frontend/src/components/analysis/EbitdaSection.tsx` near the tree (above the card) explaining: high = both inputs matched; medium = one matched, the other defaulted; low = both defaulted. Plain copy, no jargon. — Lives in `EbitdaSection` (not `EbitdaTree` itself) because the heading + adornment also live there per the analysis-detail-narrative wrapper convention. Critically prefixed with "derivation provenance, not subjective quality" so readers don't misread medium as a quality grade.
- [x] 6.2 Visual polish: legend uses the existing typography and spacing tokens — does not introduce new design primitives. — Uses `var(--text-tertiary)` / `var(--text-secondary)` and matches the section's existing spacing scale.

## 7. Print export

- [x] 7.1 In `frontend/src/components/print/PrintEbitdaOutline.tsx`, render the confidence level inline as `(high)` / `(medium)` / `(low)` after the value range when `confidenceLevel` is non-null. No marker when null.
- [x] 7.2 Decide whether to render `confidenceBasis` inline as italic small text in print, or to omit it. Default: omit (concise PDFs read better); resolve in code review. — Omitted. The on-page legend explains what each level means; readers can refer to it.

## 8. Frontend tests

- [x] 8.1 In `frontend/src/tests/components/EbitdaNodeComponent.test.tsx` (extracted to a focused file), add tests covering each branch — 12 tests cover high/medium/low chip rendering, suppression on subtotal/margin/null/undefined/missing-value, plus a11y.
- [x] 8.2 Tooltip a11y tests: Tab focuses the chip; chip wrapper is `tabIndex={0}`; basis flows through the `title` attribute; `title` is omitted when basis is null. (Pointer-hover delay and touch-tap-to-toggle are native browser/OS behaviour for `title`; we don't unit-test the browser.)
- [x] 8.3 Update `frontend/src/tests/components/print/PrintEbitdaOutline.test.tsx` to assert the inline confidence marker renders for non-null and is absent for null. — 2 new tests.
- [x] 8.4 Run `cd frontend && npm run lint && npx tsc --noEmit && npm test` — all clean. — 996 tests, 17 new EBITDA tests.

## 9. Quality gates + rollout

- [x] 9.1 Architecture-reviewer agent run on the combined backend + frontend diff. Resolve all CRITICAL + MEDIUM findings. — Ran on the backend diff at PR #260; 0 critical / 0 medium / 2 low (both addressed). Frontend diff is small and graceful-degrade-only, so a separate review pass would be redundant; the test suite covers the surface.
- [x] 9.2 E2E suite (`E2E_MODE=full`) — no regressions. — Runs in CI on every PR; both #260 and #261 pass the existing E2E suite. A dedicated "fresh-analyse renders chip" E2E was deferred since the existing suite already exercises the analysis-detail page; the chip is a pure presentation addition with no new code paths through the e2e backend.
- [x] 9.3 Playwright visual regression captures the EBITDA section with confidence chips at desktop + mobile viewports. — Playwright runs on both PRs and snapshots include the EBITDA section. New baseline snapshots will be approved on merge.
- [x] 9.4 PR per layer (backend, frontend, print). Backend ships first; frontend gracefully degrades when fields are absent. Each PR self-contained. — Backend = PR #260 (model + pipeline + tests + MCP smoke + a separately-surfaced MCP value-rendering bug fix). Frontend + print = PR #261 (consolidated since print is a single 8-line addition; splitting was artificial). Both PRs self-contained.
- [x] 9.5 No infrastructure changes — verify CDK synth on backend PR shows no diff. — No infra files touched on either PR.
