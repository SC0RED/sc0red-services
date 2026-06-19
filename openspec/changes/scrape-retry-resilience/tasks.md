## 1. Transport module + retry

- [x] 1.1 Create `src/data_strategies/scraper_transport.py`: move `fetch_page_html` + `_IMPERSONATE_TARGET` + `_SCRAPER_TIMEOUT` + curl_cffi imports out of `web_scraper_strategy.py`; add retry constants (`_FETCH_MAX_ATTEMPTS=3`, backoff, `_RETRYABLE_STATUS`).
- [x] 1.2 In `fetch_page_html`, retry on retryable HTTP status (403/408/425/429/5xx), `ConnectionError`, `Timeout` with brief backoff; raise immediately on non-retryable HTTPError (404/410) and on `ImpersonateError`; raise the last error after exhausting attempts.
- [x] 1.3 In `web_scraper_strategy.py`, import + re-export `fetch_page_html` (keep `scrape_url` calling it); keep the curl_cffi exception imports for `WebScraperStrategy.execute`. Confirm the file is back under 400 lines.

## 2. Genuine-zero vs fetch-failure

- [x] 2.1 In `PortfolioDiscoveryStrategy.execute`, when a portfolio listing page fetch raises a non-404 error (a real block/timeout after retries), record it; expose `site_fetch_failed` (bool) in the returned metadata.
- [x] 2.2 In `DiscoverPortfolio.execute`, when the web-search fallback fires, log WARNING (with cause) if `site_fetch_failed`, else INFO for a genuine empty site. Fallback firing behavior unchanged.

## 3. Tests

- [x] 3.1 `scraper_transport.fetch_page_html`: 403-then-200 → returns 200 (retry transparent); 404 → raises without retry; all-retryable → raises after `_FETCH_MAX_ATTEMPTS`; `ImpersonateError` → raises immediately. (Patch `time.sleep`.)
- [x] 3.2 `scrape_url` still parses correctly via the re-exported `fetch_page_html` (existing tests pass); `web_scraper_strategy.fetch_page_html` patch path still works.
- [x] 3.3 `PortfolioDiscoveryStrategy`: listing fetch raising a 403 (post-retry) → `site_fetch_failed=True` in metadata; a 404-only firm (no real listing) → not flagged as fetch failure.
- [x] 3.4 `DiscoverPortfolio`: fallback after `site_fetch_failed` logs the fetch-failure cause; genuine-empty does not.

## 4. Validation & verification

- [x] 4.1 `ruff check` + `ruff format` + naming validator + abbreviations clean on changed files
- [x] 4.2 `pyright src/` introduces no new error category
- [x] 4.3 `pytest tests/ -q` passes with coverage ≥ 95%
- [ ] 4.4 Run the `architecture-reviewer` agent; resolve CRITICAL before commit
- [x] 4.5 Confirm locally: `franciscopartners.com/investments` scrape still succeeds; simulate a 403-then-200 and a persistent 403 to exercise retry + surfaced fallback
- [ ] 4.6 Run the E2E suite per CLAUDE.md before opening the PR
- [ ] 4.7 After deploy: re-run Francisco Partners on dev a few times and confirm a consistent full count (no more 75/175 flip)
