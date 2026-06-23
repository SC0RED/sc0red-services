## Context

`DiscoverPortfolio.execute()` runs two paths over one scrape:
1. **Heuristic** — `PortfolioDiscoveryStrategy` crawls `PORTFOLIO_PATHS`, filters `<a>` links (external company sites or internal `/portfolio/<slug>`), and also returns `page_text` + `all_links` in its metadata.
2. **AI extraction** — `_run_ai_extraction` feeds `page_text` (+ a links list) to the model and gets back structured `{name, url}` companies.

Results are merged by domain in `_merge_results`: companies found by **both** paths → `auto_included` (high confidence, skip validation); the remainder → `needs_validation` (sent to `ValidatePortfolioCompanies`). Each surviving company is then individually scanned.

Both paths consume `scrape_url` output. `scrape_url` (`web_scraper_strategy.py`) `decompose()`s every `<script>` and extracts only visible `<body>` text + `<a>` links. For Vista/Thoma Bravo the portfolio lives in a **`<script>` JSON hydration island** (`{"name":"Sophos","slug":"sophos",…}`), and the visible body is a ~1.3 KB skeleton — so both paths get nothing.

The pipeline now also has `run_grounded_ai_call` (native `web_search`) from `ai-researched-financials`, and an `auto_included`/`needs_validation` tiering model — both reused here.

Constraints (CLAUDE.md): RequestStep + factory wiring; `run_structured_ai_call`/`run_grounded_ai_call` (no raw threads); externalized prompts/schemas; fail-fast on real bugs but fail-soft on best-effort enrichment; files < 400 lines; 95% coverage.

## Goals / Non-Goals

**Goals**
- Discover portfolios embedded as `<script>` JSON (the Vista/Thoma Bravo case) by giving the AI extractor the raw HTML, not the body skeleton.
- Recover portfolios from opaque/CSR sites via a web-search fallback that fires only when the site scrape is thin.
- Keep the firm's own site authoritative; treat web-search results as lower-confidence recall that is always validated.
- Reuse existing infra: `run_grounded_ai_call`, the heuristic path, the merge tiers, `validate_portfolio`.

**Non-Goals**
- Headless-browser rendering (Playwright/chromium) — deferred.
- Deterministic site-specific JSON parsing (`__NEXT_DATA__` walkers) — the LLM extracts from raw HTML instead, which generalizes across JSON shapes.
- Changing the heuristic link-filter or the per-company scan/validation flow.

## Decisions

### Decision 1: Feed the AI extractor raw HTML (incl. `<script>`), not `page_text`
The companies are in the response — inside `<script>` JSON we currently delete. Expose the **raw HTML** from the scrape (the strategy already fetches it) and pass a budgeted slice to `_run_ai_extraction`, replacing the skeleton `page_text` as the primary content. The model extracts `{name, url}` from the embedded JSON just as it would from visible text.

- **Token budget:** raw HTML is large (~409 KB, 72 scripts). Prefer a **script-aware selection**: concatenate the text of `<script>` tags that look data-bearing (contain many quoted `"name"`/`"slug"` keys, or are the largest blobs), plus the visible body text, truncated to a budget comparable to today's `_AI_PAGE_TEXT_BUDGET`. Fallback to a raw-HTML head-slice if no script stands out. (Exact selection heuristic is an implementation detail settled against real pages — Vista + Thoma Bravo as fixtures.)
- The heuristic link-filter path is **unchanged** — it still wins for sites that expose companies as anchors/external links, and its intersection with the AI path still drives `auto_included`.

### Decision 2: Web-search fallback as a separate, conditional step — site-first
Add a fallback that runs **only when site-derived discovery is below a low-water mark**. It uses `run_grounded_ai_call` with the `web_search` tool to ask for the firm's notable current portfolio companies, returning `{name, url}` candidates.

- **Why conditional, not parallel-union:** the firm's site is the source of truth (current portfolio); web search is recall and can surface **stale/divested** companies or hallucinations. Union would pollute a clean site list and pay search cost every scan. Conditional keeps the common case cheap and the fallback strictly additive.
- **Trigger:** `total_site_companies < THRESHOLD`, `THRESHOLD` configurable, default **0** (rescue clear failures). Tunable upward later to catch thin/partial scrapes.
- **Placement:** invoked from `DiscoverPortfolio.execute()` after the site merge, before emitting details. Keep it a focused helper/step that goes through `run_grounded_ai_call` (single shared AI path).

### Decision 3: Fallback candidates land in `needs_validation`, never `auto_included`
Model-sourced candidates are unioned into `needs_validation` (deduped by normalized domain against site results), so `ValidatePortfolioCompanies` AI-validates every one before it's scanned. This mirrors the existing tiering and the fact-vs-forecast line: discovery is a *validated candidate list*, not an asserted fact. `auto_included` remains reserved for the high-confidence heuristic∩AI intersection from the firm's own site.

### Decision 4: Fail-soft enrichment
The fallback is best-effort. A `web_search`/AI failure (rate limit, schema error, empty result) yields **no extra candidates** and logs — it does **not** raise or fail the scan. (Contrast with fail-fast on real bugs: programming errors still propagate.) A zero-from-site + failed-fallback scan reports the existing "could not identify portfolio companies" diagnostic.

### Decision 5: Prompt + schema externalized
New fallback prompt (`prompts/templates/...`) + short output schema (`prompts/schemas/...`) for `{companies:[{name,url}], …}`, loaded via the existing loader. The system prompt instructs: return the firm's *current* notable portfolio companies with their official site URLs; prefer current holdings over exited/divested; this is a candidate list that will be validated.

## Risks / Trade-offs

- **[Raw HTML blows the token budget / dilutes signal]** → Mitigation: script-aware selection (data-bearing `<script>` blobs first) + truncation; measure extraction quality on Vista/Thoma Bravo fixtures.
- **[Fallback surfaces stale/divested companies]** → Mitigation: `needs_validation` tier + per-company scan catch them; prompt asks for current holdings; fallback only fires on low yield.
- **[Web-search cost creep]** → Mitigation: conditional trigger means search runs only on thin scrapes, not every portfolio scan.
- **[Raw-HTML extraction false positives (e.g., partner logos, news mentions)]** → Mitigation: same validation tier; the AI extraction prompt already scopes to portfolio companies.
- **[Sites that are pure CSR with NO embedded data and unknown to the model]** → Accepted residual; the documented Playwright option remains the escalation if this proves common.

## Migration Plan

1. Expose raw HTML / data-bearing script text from the scrape path (additive to strategy metadata).
2. Point `_run_ai_extraction` at the richer content (behaviour change for the AI path only; heuristic unchanged).
3. Add the conditional web-search fallback + its prompt/schema; union into `needs_validation`.
4. No persistence/schema migration — discovery output shape (`portfolio_companies`, `auto_included`, count, diagnostic) is unchanged; only the *contents* improve.
5. Rollback: revert the branch; discovery returns to today's behaviour.

## Open Questions

- Exact data-bearing `<script>` selection + truncation heuristic for Decision 1 — settle against Vista + Thoma Bravo fixtures during implementation.
- Final default threshold for Decision 2 (start 0; revisit after observing real low-yield rates).

## Documented Next Step (out of scope)

**Headless-browser rendering (Playwright).** For truly client-side-only sites with no embedded data and no model recall, rendering + hydrating the DOM is the last resort. Deferred due to operational cost (chromium-in-Lambda, latency); revisit only if #1+#4 leave a meaningful gap.
