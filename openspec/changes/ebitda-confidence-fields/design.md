## Context

The EBITDA tree on the analysis-detail page is rendered from `EbitdaTreeResult`, a deterministic decomposition built by `build_programmatic_ebitda_tree` (`backend/src/pipeline/pipeline_steps/build_ebitda_tree.py`). The function reads `CompanyProfile` (business model, company size, name, industry) and produces a tree of `EbitdaNode` records with `value_range` strings like `"$2M-$8M"` and percentages of parent. There is no AI call in this step — the figures come from industry-benchmark templates (`_Template`) and a `_SIZE_TO_EMPLOYEES` lookup.

PE buyers consistently signal that point estimates without provenance fail the trust bar — the ranges are accepted, but only when the analyst can answer "where did this number come from?" Right now the answer requires reading source code.

The good news: the function already knows, at construction time, *which* derivation path each node took. A revenue node anchored to a scraped declared figure on the company profile is structurally different from one extrapolated from a size-bracket default, but both currently render identically. We just stop discarding that signal and surface it as a confidence chip.

This is intentionally not an AI self-rating. AI confidence labels are notoriously unreliable when models hallucinate confidently. Derivation provenance is *deterministic*, *auditable*, and *defensible* — the same inputs always yield the same confidence label, and the basis string explains exactly which input drove it.

## Goals / Non-Goals

**Goals:**

- Surface derivation provenance per EBITDA tree node as a confidence level (high/medium/low) plus a 1–2 sentence basis string.
- Render the level as a chip on each leaf node in `EbitdaNodeComponent`, with the basis exposed via hover/focus tooltip.
- Print export reflects the confidence level inline so PDF readers see it.
- Preserve backward compatibility: existing analyses without the fields render with the chip suppressed, no "unknown" badge.
- Keep the change additive across data layers (Pydantic model, DynamoDB JSON, frontend types) so re-analysis is the only path to the new signal — no backfill job required.

**Non-Goals:**

- AI self-rated confidence. Out of scope and explicitly avoided — see Decisions §1.
- Numeric confidence intervals or probability scores (e.g., "72% confident"). The level/basis pair is enough; numerals would imply false precision.
- Changing the EBITDA tree's deterministic computation. The provenance signal is a *byproduct* of the existing logic, not a new computation.
- Surfacing confidence on rollup/subtotal nodes. Rollups inherit from children; chip-on-rollup would double-count the signal and add visual noise.
- Onboarding new users to interpret confidence (separate change if we add an "EBITDA tree explained" walkthrough).

## Decisions

### 1. Confidence is derivation provenance, not AI self-rating

**Decision:** The confidence level is a deterministic label derived from *which input drove the node's value_range*. Not an AI call.

**Why:**

- Auditable. A PE analyst can ask "why is this medium?" and the basis string answers it directly ("Inferred from company-size bracket × industry-benchmark margin").
- Reproducible. Same `CompanyProfile` inputs → same confidence labels every time. No drift across pipeline runs.
- Avoids the "AI confident but wrong" failure mode. AI self-rating is well-known to be miscalibrated.
- The information is *already in the code path* — `build_programmatic_ebitda_tree` knows which template branch fired. We're not adding a computation, we're stopping the discard.

**Alternatives considered:**

- **AI self-rated confidence**: rejected. Brittle, expensive (extra prompt round-trip), and well-documented to be miscalibrated. PE workflows demand auditable provenance, not model self-assessment.
- **Numeric probability score**: rejected. Implies false precision. A 3-level scale matches the rest of the page's `ConfidenceIndicator` palette.

### 2. Three levels: high / medium / low

**Decision:**

| Level | Trigger |
|---|---|
| `high` | Anchored to a scraped or declared figure on `CompanyProfile` (e.g., revenue stated on the company website / About page) |
| `medium` | Inferred from a known company-specific input (`company_size` → employee count → revenue) crossed with an industry benchmark from `_Template` |
| `low` | Defaulted from a size bracket / industry template with no company-specific anchor (e.g., `_DEFAULT_EMPLOYEES` fallback fired) |

**Why:** Three is the smallest scale that distinguishes the three meaningful provenance classes. Two would collapse "anchored" and "benchmarked" into a single bucket, which is exactly the distinction PE analysts need. Five would over-fragment a deterministic signal.

**Alternatives considered:**

- **Two levels** (anchored vs inferred): rejected. The benchmark-with-input case is materially different from the "we have no signal at all" default case.
- **Five levels**: rejected. The build logic only has three meaningful provenance branches today; sub-levels would invite arbitrary thresholding.

### 3. Suppression when null, not "unknown" badge

**Decision:** Frontend renders the chip only when `confidenceLevel` is non-null. Old records (pre-change) render without a chip. No "unknown" / "—" / question-mark badge.

**Why:** Silence is more honest than a badge that admits uncertainty about uncertainty. A PE analyst seeing an "unknown" badge would reasonably ask "well, why don't you know?" — and the answer is "this analysis predates the field" which has zero bearing on whether the figure is trustworthy. Hiding the chip avoids that distraction. The fail-fast principle from CLAUDE.md says required fields use `record["key"]` to surface bugs; this is an *optional* additive field, where the right behavior is graceful degradation.

**Alternatives considered:**

- **"Unknown" / question-mark badge**: rejected per above.
- **Backfill job to assign confidence to existing records**: rejected. Re-analysis is the natural path; old records will gain the field on the next user-triggered re-analysis. Backfill adds complexity for negligible benefit (the user-visible delta is identical 24 hours later).

### 4. Chip uses the existing `ConfidenceIndicator` 3-dot scale

**Decision:** Reuse `frontend/src/components/analysis/ConfidenceIndicator.tsx` (shipped via the analysis-detail-narrative work). Map `high → 3 dots`, `medium → 2 dots`, `low → 1 dot`.

**Why:** Pattern consistency. The component is already on the page in other contexts; using a different chip style for EBITDA would force users to learn two scales. CLAUDE.md mandates pattern consistency.

**Alternatives considered:**

- **Color-coded badge** (green/yellow/red): rejected. Risk-tier semantics already use color on the page (Critical/High/Moderate/Low risk). Reusing color for a different concept causes a category collision in the visual language.

### 5. Tooltip rendered via existing `HelpTooltip` primitive

**Decision:** Hover/focus on the chip reveals `confidenceBasis` via the existing `HelpTooltip` component (shipped via webapp-ux-foundations-tier2 §2). The tooltip body is rendered from `confidenceBasis` directly — not via the help-content registry — because the basis is per-node, not per-term.

**Why:** `HelpTooltip` already handles ARIA (`role="tooltip"`, `aria-describedby`), keyboard focus, and touch-tap behavior. Adding a new tooltip primitive would violate pattern consistency. The registry is for shared terms (Risk Tier, EBITDA Tree, etc.); per-node basis text is content, not terminology.

**Implementation note:** `HelpTooltip` will need a `content` prop variant (today it takes a registry `term` key only). This is a small additive prop — not a breaking change.

### 6. Print export renders confidence inline as text

**Decision:** `PrintEbitdaOutline` (used in PDF export) renders confidence as plain text — `(high)`, `(medium)`, `(low)` — appended to each node's value range. No chip glyph in print.

**Why:** Print medium can't render hover-for-basis, so the chip would be misleading there (showing the level without affording the rationale). Inline text is print-native. The basis string can be optionally rendered inline (small italics) when present — to be decided in implementation per the polished-pdf-export aesthetic.

## Risks / Trade-offs

- **[Risk]** Provenance tagging mistakenly surfaces `low` when a node was actually anchored to a declared figure. → **Mitigation:** Branch coverage in `test_build_ebitda_tree.py` for every `_Template` × company-profile combination that decides confidence. Each branch in the build function asserts the confidence label that branch produces.

- **[Risk]** PE users misread `medium` as a quality score (interpreting it as "the answer might be wrong") rather than a provenance label (interpreting it as "we used industry benchmarks here"). → **Mitigation:** The legend in `EbitdaTree` documents the meaning explicitly: "high = anchored to declared data; medium = inferred from company size + industry benchmark; low = defaulted from a size bracket." The basis string per node reinforces this.

- **[Risk]** Schema bump to `EbitdaTreeResult` v2 silently breaks consumers that strict-validate the shape. → **Mitigation:** Added fields are optional with `None` default; Pydantic `BaseModel` accepts old records. No serialization changes. The MCP server (which reads `EbitdaTreeResult`) is the only known external consumer; it accepts unknown extra fields by default. Add an MCP smoke test asserting the new fields don't break the existing tool surface.

- **[Risk]** Hover tooltip on small chips fails on touch devices. → **Mitigation:** `HelpTooltip` already handles this (tap-to-toggle on touch). Vitest tests cover the touch-tap path.

- **[Risk]** Confidence chips visually crowd the EBITDA tree on small viewports. → **Mitigation:** Chip is the smallest variant of `ConfidenceIndicator` (3 dots, no label text). On viewports < 768px, the chip stays inline with the value range; design verified via Playwright visual regression on the relevant analysis-detail snapshot.

## Migration Plan

1. **Backend first** — model field addition + build logic + tests + schema doc update. Lands as one PR.
2. **Frontend second** — type addition + chip rendering + legend + tests. Lands as a second PR. Frontend gracefully degrades when backend hasn't shipped (optional field renders nothing).
3. **Print export** — small follow-up, lands separately or with the frontend PR depending on scope.
4. **No infra deploy required.** Lambda picks up the new pipeline output on next analysis run; existing records remain valid.

**Rollback:** purely additive — revert any of the three PRs in any order. No migrations, no schema rewrites.

## Open Questions

- (None blocking.) All decisions above are settled by the architecture and existing patterns. Implementation will surface only minor tactical choices (e.g., chip alignment in `EbitdaNodeComponent`) which are appropriate to resolve in code review rather than design.
