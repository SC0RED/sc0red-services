## 1. Expose raw HTML / data-bearing scripts from the scrape

- [ ] 1.1 In `web_scraper_strategy.scrape_url`, capture the raw response HTML and the concatenated text of `<script>` tags (before/instead of discarding them) and return them additively (e.g. `raw_html`, `script_text`) alongside the existing `text`/`links` — without changing existing consumers
- [ ] 1.2 Add a helper to select the data-bearing content for AI extraction: prefer `<script>` blobs that look like data (many quoted `"name"`/`"slug"` keys, or the largest blob) + visible body text, truncated to a budget; fall back to a raw-HTML head-slice
- [ ] 1.3 Thread the raw HTML / script text through `PortfolioDiscoveryStrategy.execute()` metadata (additive to `page_text`/`all_links`)
- [ ] 1.4 Unit tests: a script-embedded portfolio (Vista/Thoma Bravo-shaped fixture) exposes the JSON content; anchor-linked sites unchanged; budget/truncation respected

## 2. AI extraction reads raw HTML (fix #1)

- [ ] 2.1 Point `DiscoverPortfolio._run_ai_extraction` at the data-bearing raw-HTML/script content instead of the cleaned `page_text` skeleton (keep the links list)
- [ ] 2.2 Update the extraction prompt (`prompts/templates/extract_portfolio_companies.md`) if needed so the model knows it may be reading raw HTML / embedded JSON, and the schema is unchanged (`{name, url}`)
- [ ] 2.3 Tests: AI extraction over a script-JSON fixture returns the embedded companies (was zero); heuristic path untouched

## 3. Web-search fallback (fix #4)

- [ ] 3.1 Author the fallback prompt (`prompts/templates/...`) + short output schema (`prompts/schemas/...`): firm URL/name in → `{companies:[{name,url}]}` out; instruct "current notable portfolio, prefer current over divested, official site URLs, this is a candidate list that will be validated"
- [ ] 3.2 Add a fallback helper/method that runs `run_grounded_ai_call` (native `web_search`) and returns candidates; fail-soft (errors/empty → no candidates, no raise)
- [ ] 3.3 Add a configurable low-water-mark threshold (default 0) for when the fallback fires

## 4. Wire the fallback into discovery (conditional, additive, validation-tier)

- [ ] 4.1 In `DiscoverPortfolio.execute()`, after the site merge, if `total_site_companies < THRESHOLD` run the fallback
- [ ] 4.2 Union fallback candidates into `needs_validation` only (dedup by normalized domain against site results); never `auto_included`
- [ ] 4.3 Only emit the existing "0 results" diagnostic when site + fallback both yield nothing; add INFO logging for fallback fired / candidates / final count
- [ ] 4.4 Tests: low yield → fallback fires + candidates land in needs_validation; healthy site → fallback skipped; fallback failure → fails soft with existing diagnostic; dedup against site companies

## 5. Validation & verification

- [ ] 5.1 `ruff check` + `ruff format` + naming validator + abbreviations clean on changed files
- [ ] 5.2 `pyright src/` introduces no new error category
- [ ] 5.3 `pytest tests/ -q` passes with coverage ≥ 95%
- [ ] 5.4 Run the `architecture-reviewer` agent; resolve CRITICAL before commit
- [ ] 5.5 Reproduce the customer case: Vista + Thoma Bravo fixtures now yield companies (via #1); confirm the fallback path on a synthetic low-yield case
- [ ] 5.6 Run the E2E suite per CLAUDE.md before opening the PR (extend the mock-AI server if the discovery path exercises the new extraction/fallback prompts)

## 6. Documented next step (do NOT implement here)

- [ ] 6.1 Confirm the deferred headless-browser (Playwright) option is recorded in design.md as the escalation if #1+#4 leave a gap — do not build it in this change
