## Why

The polished PDF export shipped a working pipeline (Lambda + Puppeteer + signed URL tokens), but the *content* of the rendered PDF reuses the live screen components verbatim — components designed for an interactive UI with collapse-by-default, zoom/pan controls, and horizontal-flex layouts. The result is a document that surfaces only ~30% of the underlying analysis: risk scores show without rationales, opportunity cards show without descriptions or implementation steps, the EBITDA tree renders only its top level (with interactive UI chrome bleeding through), the value chain is horizontally cut off mid-page, and the sc0red CTA appears twice. PE buy-side users have asked for a PDF they can attach to an investment memo or hand to a portfolio CFO — the current artifact does not meet that bar.

## What Changes

- Introduce a dedicated set of **print-specific React components** under `frontend/src/components/print/` that render the same `AnalysisData` for paper rather than for screen — fixes the structural mismatch (collapsed-by-default, interactive controls, horizontal layouts) that caused every issue users flagged.
- Add an **Executive Summary** page between the cover and the Risk Assessment, anchored by an EBITDA-uplift bar, top-3 opportunity one-liners, and the three highest-weighted risk drivers. This is the "skim in 5 minutes" page for the deal partner.
- Render the **Risk Profile** as fixed-expanded rows that always show each category's `rationale` text (currently hidden behind a chevron).
- Render the **AI Opportunity Roadmap** as one expanded card per opportunity, surfacing `description`, `implementation_steps`, `investment_range`, and `roi_estimate` (all currently in the model but invisible in the PDF). Group cards by `value_lever` (Revenue / Cost / Both) with section dividers.
- Replace the interactive `EbitdaTree` in the print path with a **static fully-expanded rendering** (SVG or nested outline) on a landscape page, plus a "linked opportunities" callout per branch using the existing `linked_opportunity_indices` linkage data.
- Replace the horizontal `ValueChainDiagram` in the print path with a **vertical, page-friendly layout** (stacked rows, primary then support), with per-step risk chips and an `opportunity_indices` linkage callout.
- Add a **Methodology Appendix** half-page (sources scraped, model, scoring rubric, AI-disclosure disclaimer) — credibility move for paranoid PE readers.
- Move the **sc0red CTA to a single back-cover page**; remove its current in-document occurrences inside `OpportunitiesList` and `ValueChainDiagram` for the print path.
- Add a **per-section page-format override** so the EBITDA tree page can be A3 landscape while the rest of the document is A4 portrait.
- **BREAKING (visual only)**: the rendered PDF for a given analysis is materially different. The export endpoint contract, filename pattern, auth flow, signed-token TTL, analytics event, and binary-PDF response are unchanged.

## Capabilities

### New Capabilities
<!-- None — this extends the existing in-flight polished-pdf-export capability. -->

### Modified Capabilities
- `polished-pdf-export`: extends the existing capability (still in-flight via the `polished-pdf-export` change) with content-quality requirements — the rendered PDF must surface a defined set of `AnalysisData` fields, follow a defined structural ToC, and use print-specific layouts rather than reusing interactive screen components.

## Impact

- **Frontend**: new `frontend/src/components/print/` directory with 4–6 print-specific components (`PrintExecutiveSummary`, `PrintRiskTable`, `PrintOpportunityCard`, `PrintEbitdaOutline`, `PrintValueChainList`, `PrintMethodologyAppendix`). `frontend/src/app/print/[analysisId]/PrintReport.tsx` is rewritten to compose these instead of the live screen components. `frontend/src/app/print/print.css` gains per-section `@page` rules.
- **Backend / infrastructure**: no changes. The Puppeteer Lambda, signed-token flow, and Cognito-gated proxy stay as-is.
- **Tests**: new RTL tests for each print component; the existing print-route smoke test gets extended to assert presence of the new sections (Executive Summary, Methodology Appendix) and absence of the duplicate CTA.
- **Observability**: no new metrics. Existing `pdf_render_failed` / `pdf_render_succeeded` filters continue to apply.
- **Data model**: zero schema changes — every field used is already on `AnalysisData`.
- **Dependencies**: no new npm packages required (SVG rendering uses inline SVG; outline fallback is plain HTML).
- **Visual regression**: the rendered PDF for an existing analysis will differ. Pre-rollout, run side-by-side comparisons on 3–5 representative analyses and capture before/after PDFs in the change folder for review.
