## Why

Portfolio discovery returns **zero companies** for major PE firms — confirmed on Vista Equity Partners and Thoma Bravo, via both the UI and the MCP `start_portfolio_scan`. Yet Claude Code (using its own knowledge) lists ~10 portfolio companies for each. The firms' sites are healthy and full of data — we just can't see it.

**Root cause (diagnosed with evidence, not theory):**
- A raw fetch of `thomabravo.com/portfolio` returns HTTP 200, ~409 KB, server-rendered, with the company names in the HTML (`<title>Our Portfolio Companies | Thoma Bravo</title>`). Vista `/companies` is similar (~484 KB). **Not blocked, not a dead site.**
- The scraper `scrape_url` returns only **~572 chars of text and 0 links** from that same 409 KB.
- `lxml` and `html.parser` produce identical output — **not a parser bug.**
- "Sophos" appears 9× in the HTML, **all inside `<script>` tags** (`{"id":125,"name":"Sophos","slug":"sophos",…}` — a Next.js-style JSON hydration island), **0× in the visible `<body>`**. The visible body is a ~1.3 KB skeleton; the cards are painted client-side from embedded JSON.
- `scrape_url` (a) `decompose()`s every `<script>` — deleting the exact JSON that holds the companies — and (b) extracts only visible body text + `<a>` links. So **both** discovery paths (heuristic link-filter and AI extraction on `page_text`) see only the skeleton → zero.
- Claude Code succeeded because it used training knowledge, not scraping. Our AI extraction reads the cleaned scraped text — not the embedded JSON, and not the model's world knowledge.

## What Changes

- **Fix #1 — AI extraction reads the raw HTML (incl. `<script>` JSON), not the cleaned body skeleton.** The company data is already in the response; we stop discarding the part that has it. The AI extracts the portfolio from the embedded JSON. Token budget is handled by selecting/truncating intelligently (largest JSON `<script>` blobs and/or a raw-HTML slice within the existing extraction budget). The deterministic heuristic link-filter path is unchanged (it still serves sites that link companies as anchors).
- **Fix #4 — conditional web-search-grounded fallback.** When the site-derived discovery yields too few companies, run a `web_search`-grounded AI call (reusing `run_grounded_ai_call` from `ai-researched-financials`) to recover the firm's notable portfolio — what Claude Code did. **Site-first, fallback-on-low-yield — not parallel union**: the firm's own site is authoritative; web search is recall (prone to stale/divested companies). The fallback is strictly additive (turns a zero into something), fires only when the scrape comes up short, and is skipped in the common case so we don't pay search cost/latency when the site already answered.
- **Low-water-mark trigger**, starting at 0 (rescue clear failures) and configurable so it can be raised after seeing real data.
- **Fallback candidates enter the existing `needs_validation` tier** (never `auto_included`), so model-sourced names are always AI-validated by `validate_portfolio` before each survivor is individually scanned.
- **Fail-soft:** a web-search failure yields no extra candidates — it never crashes the scan.

## Capabilities

### New Capabilities
- `portfolio-discovery-web-fallback`: a web-search-grounded discovery fallback that runs only when site-derived discovery is below a configurable low-water mark; recovers the firm's portfolio via `run_grounded_ai_call`; fails soft; emits candidates into the needs-validation tier.

### Modified Capabilities
- `portfolio-discovery-recall`: the AI-extraction input is now the **raw HTML including `<script>` JSON islands** (intelligently selected/truncated to the budget), not the cleaned visible-body text — so portfolios embedded as hydration JSON are discoverable.
- `discovery-merging`: web-search-fallback candidates merge into `needs_validation` (never `auto_included`); the "0 results" path triggers the fallback before reporting an empty discovery.

## Impact

- **Backend pipeline:** `discover_portfolio.py` (orchestration: build the AI-extraction input from raw HTML; invoke the fallback on low yield; merge fallback into needs_validation), a new web-search fallback step/helper (RequestStep-wired, via `run_grounded_ai_call`), new prompt+schema under `src/pipeline/prompts/` for the fallback, and a raw-HTML/`<script>`-selection helper around `web_scraper_strategy`/`discover_portfolio`.
- **Unchanged:** the heuristic link-filter (`portfolio_discovery_strategy.py`) and `validate_portfolio.py` (fallback candidates flow through existing validation).
- **Cost/latency:** web search (~$0.01/search) only on the low-yield path; the common case (site answers) is unchanged. Portfolio scans are already async.
- **Out of scope (documented next step):** headless-browser rendering (Playwright/chromium-in-Lambda) — deferred; #1+#4 should cover embedded-JSON and opaque-CSR sites without the operational cost.
