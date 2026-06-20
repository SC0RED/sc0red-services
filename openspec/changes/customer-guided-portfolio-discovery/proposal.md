## Why

Portfolio discovery has a hard floor: some firms (e.g. Insight Partners, 300+ holdings) render their portfolio entirely client-side, so the static scrape finds nothing and the web-search fallback returns only a handful of well-known names (3). No amount of parsing recovers a list that isn't in the HTML. Today the customer just sees a small, unexplained number with no way to tell *why* it's short or to *correct* it — which reads as "the product is broken."

The fix is a product shift, not another parser: make discovery **transparent and customer-guided**. Run the cheap methods first, tell the customer plainly what we found and why it may be incomplete, and give them explicit choices to dig deeper or supply the list themselves — rather than silently presenting a partial result as the answer.

## What Changes

- **Discovery verdict + meaningful messaging.** Discovery emits a structured outcome — the method that produced the result, the count, a completeness signal (full site list / site blocked / web-search subset / genuinely empty), and the next actions available — which the UI renders as a clear message instead of a bare number. E.g. "This firm's site loads its portfolio dynamically, so we couldn't read it directly. A quick search found 3 well-known companies; this firm likely has more."
- **Customer-gated escalation ladder.** After the quick automatic pass, the confirmation screen offers explicit, cost-aware choices: **Search deeper** (a broader/multi-pass web search), and — as a documented opt-in rung — **Render the site** (headless browser; deferred implementation, surfaced as a choice). Expensive methods run only when the customer chooses them.
- **Customer company-list upload (CSV/PDF).** The reliable correction path: the customer uploads a CSV or PDF listing the portfolio companies; we parse it into discovery candidates that flow through the existing validation → scan path. Works for any site we can't fully crack.

## Capabilities

### New Capabilities
- `portfolio-discovery-verdict`: discovery returns a structured, customer-facing verdict (method, count, completeness signal, available next actions) rendered as a meaningful message rather than a bare count.
- `portfolio-discovery-escalation`: customer-triggered escalation of discovery (deeper web search now; headless render as a documented opt-in rung) from the confirmation screen, so expensive methods run only on explicit request.
- `portfolio-company-list-upload`: customer uploads a CSV/PDF of portfolio companies, parsed into discovery candidates and run through the existing validation/scan path.

### Modified Capabilities
- `async-portfolio-scan`: the portfolio scan flow carries the discovery verdict and supports re-entering discovery for a customer-chosen escalation (rather than a one-shot pass).

## Impact

- **Backend:** `DiscoverPortfolio` emits the verdict (method/count/completeness/next-actions); `scan_core` gains a "deepen"/escalate entry that re-runs discovery at a chosen tier; a CSV/PDF → company-candidates path reusing `src/documents/extract_text.py`; the web-search fallback gains a broader "deeper" mode.
- **Frontend:** the confirmation screen renders the verdict message + escalation choices (Search deeper / Render the site / Upload a list) and a CSV/PDF uploader (reuses the existing document-upload UI from the report-data-integrity work).
- **Phasing:** Phase 1 — verdict + messaging + CSV/PDF upload (transparency + correction, no heavy infra). Phase 2 — deeper web-search rung. Phase 3 (documented, deferred) — headless-render rung behind the customer opt-in.
- **Out of scope (this change):** building the headless-render (Playwright) engine itself — it is defined as an opt-in escalation rung and deferred to its own change; reverse-engineering firm-specific portfolio APIs.
