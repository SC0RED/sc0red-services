## 1. Add the curl_cffi dependency

- [x] 1.1 Add `curl_cffi` to `backend/pyproject.toml` dependencies; run `uv lock` and confirm the resolved version + a current impersonation target (e.g. latest stable chrome it ships)
- [x] 1.2 Confirm the `curl_cffi` manylinux wheel resolves in the `python:3.12-slim` CDK bundling image for the configured Lambda architecture (`x86_64` and/or `aarch64` per `arch_value`)

## 2. Switch the scraping transport to curl_cffi

- [x] 2.1 In `web_scraper_strategy.scrape_url`, replace the `httpx.Client(...).get(...)` + `raise_for_status()` with `curl_cffi.requests.get(url, impersonate=<current target const>, timeout=SCRAPER_TIMEOUT, allow_redirects=True)` + `raise_for_status()`; drop the hand-rolled `SCRAPER_HEADERS` on the impersonated path (transport owns headers). Keep BeautifulSoup parsing, `_extract_data_scripts`, and the return dict unchanged
- [x] 2.2 Add a module-level impersonation-target constant (single current browser) with a comment documenting the staleness maintenance note
- [x] 2.3 Update `WebScraperStrategy.execute()` except clauses from `httpx.HTTPStatusError`/`httpx.RequestError` to the `curl_cffi` equivalents (`HTTPError` for status, `RequestException`/`ConnectionError`/`Timeout` for transport); preserve the existing empty-text + `metadata["error"]` contract; ensure programming errors are NOT caught
- [x] 2.4 In `portfolio_discovery_strategy.py`, reconcile the `httpx` import/except around the `scrape_url` loop (it currently catches broad `Exception` — narrow to the expected transport errors, keep fail-soft per-page behavior)
- [x] 2.5 Confirm `httpx` is still imported only where genuinely used (`tracing.py`, `worker_handler_entry.py`); leave it as a dependency

## 3. Surface the real scrape-failure cause

- [x] 3.1 In `ScrapeAndResolveURL.execute()`, when content is insufficient, include the underlying `metadata["error"]` / HTTP status in the raised message (e.g. "...blocked: HTTP 403") when one is known; keep the plain "insufficient content" message for a genuine thin-but-200 page
- [x] 3.2 Update the resolved-URL scrape `try/except` (`httpx.RequestError, httpx.HTTPStatusError`) to the `curl_cffi` exception types

## 4. Tests

- [x] 4.1 `scrape_url` success path (mock `curl_cffi` returning 200 HTML) → title/text/links/script_text parsed as before; impersonation target passed through
- [x] 4.2 `scrape_url` redirect followed; `WebScraperStrategy.execute` HTTPError (e.g. 403) → empty text + `metadata["error"]`; transport error (connection/timeout) → empty text + error; programming error propagates (not swallowed)
- [x] 4.3 `ScrapeAndResolveURL` error-surfacing: 403 → message includes HTTP status; genuine thin 200 page → plain insufficient-content message
- [x] 4.4 `portfolio_discovery_strategy` per-page fail-soft preserved under the new exception types

## 5. Validation & verification

- [x] 5.1 `ruff check` + `ruff format` + naming validator + abbreviations clean on changed files
- [x] 5.2 `pyright src/` introduces no new error category
- [x] 5.3 `pytest tests/ -q` passes with coverage ≥ 95%
- [x] 5.4 Run the `architecture-reviewer` agent; resolve CRITICAL before commit
- [x] 5.5 Reproduce the customer case: `gainsight.com` now scrapes full content via the impersonating transport (local check)
- [x] 5.6 Run the E2E suite per CLAUDE.md before opening the PR; confirm `curl_cffi` fetches the `ai-mock` company HTML over plain http (extend the mock/compose only if needed)

## 6. Documented next step (do NOT implement here)

- [x] 6.1 Confirm design.md records Playwright as the deferred escalation for pure client-side-rendered sites (case C) and impersonation-target rotation as a deferred follow-up
