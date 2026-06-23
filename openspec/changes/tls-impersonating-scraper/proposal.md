## Why

Company scans silently fail for sites behind TLS-fingerprint bot protection. A real customer case: Gainsight (`https://www.gainsight.com/`), surfaced as a Vista Equity Partners portfolio company, failed with "Insufficient content scraped" even though the site loads normally in Chrome. Local diagnosis: the site is behind Cloudflare bot management, which fingerprints the **TLS handshake / HTTP-2 client (JA3)** — not headers — and returns HTTP 403 to our `httpx` scraper. The full server-rendered HTML is present; we just never get past the gate. Proven locally: `httpx` (HTTP/1.1 and HTTP/2, full browser headers) → 403; `curl_cffi` impersonating a current browser fingerprint (chrome131/safari18/firefox135) → 200 with the complete 243 KB page. A second, compounding bug masked the cause: the 403 was swallowed into the generic "insufficient content" message, so it took a local repro to find.

## What Changes

- **BREAKING (internal transport):** Switch the web-scraping transport from `httpx` to `curl_cffi` with browser impersonation as the **sole** scraping transport. `curl_cffi` uses libcurl + BoringSSL to present a real-browser TLS/HTTP-2 fingerprint, passing fingerprint-based bot protection. Measured equal-or-faster per request and faster to import; cost is ~6.7 MB added to the Lambda artifact.
- Impersonate a single **current** browser target (stale targets like chrome120/124 are themselves blocked). On the impersonated path, let `curl_cffi` emit its browser-consistent header set instead of the hand-rolled `SCRAPER_HEADERS` (custom headers break fingerprint coherence).
- Update the scraper's exception handling to `curl_cffi`'s error taxonomy (`HTTPError` for bad status, `RequestException`/`ConnectionError`/`Timeout` for transport) — preserving strict fail-fast (programming errors still propagate).
- **Surface the real failure cause:** when a scrape yields too little content, include the underlying HTTP status / scrape error in the message (e.g. "...blocked: HTTP 403") instead of always reporting generic "insufficient content".
- `httpx` **remains** a dependency (still used by `tracing.py` and `worker_handler_entry.py`); it is only removed from the scraping path. `curl_cffi` is added to backend dependencies.
- BeautifulSoup parsing, the `_extract_data_scripts` embedded-JSON logic (from `resilient-portfolio-discovery`), and the `_MIN_CONTENT_LENGTH` threshold are unchanged.

## Capabilities

### New Capabilities
- `scraper-bot-protection-resilience`: The web scraper fetches via a browser-impersonating TLS transport (`curl_cffi`) as its sole transport so that fingerprint-based bot protection (Cloudflare JA3) serves full content; and scrape failures surface the underlying HTTP status / error so blocks are diagnosable rather than masked as "insufficient content".

### Modified Capabilities
<!-- None: no existing spec defines the scraping transport or the scrape-failure error contract; both are introduced by the new capability above. -->

## Impact

- **Code:** `src/data_strategies/web_scraper_strategy.py` (`scrape_url` fetch + `WebScraperStrategy.execute` except clauses — the single fetch chokepoint, so all three callers benefit), `src/data_strategies/portfolio_discovery_strategy.py` (reconcile its `httpx` import/except around the `scrape_url` loop), `src/pipeline/pipeline_steps/scrape_and_resolve.py` (resolved-URL scrape except types + the error-surfacing message).
- **Dependencies:** add `curl_cffi` to `backend/pyproject.toml`; ships manylinux wheels (bundled libcurl + BoringSSL) for both `x86_64` and `aarch64`, matching the `arch_value` switch in `sc0red_services_stack.py`. Verify the wheel resolves in the `python:3.12-slim` CDK bundling image for the configured Lambda architecture.
- **Operational:** a native C dependency now sits on the critical path of every scrape (accepted trade-off for simplicity/recall/speed; blast-radius mitigated by solid error handling, not a fallback). Maintenance note: the pinned impersonation target ages — keep `curl_cffi` reasonably fresh.
- **Out of scope:** headless-browser rendering (Playwright) remains the documented escalation for pure client-side-rendered sites with no HTML/embedded data at all; impersonation-target rotation is deferred unless a single current target is observed to go stale.
