## Context

Francisco discovery returned 175 (site scrape) and 75 (web-search fallback) 13 minutes apart on the same deployed code. The fallback fires only when the worker's site fetch yields ~0. Local scraping is deterministic/healthy; the worker (Lambda datacenter IP) intermittently fails the fetch of the 835 KB `/investments` page — Cloudflare challenges datacenter IPs harder (IP reputation, beyond the JA3 impersonation from #420), and the page can approach the 15 s timeout. The single-attempt fetch + silent fallback turns a flaky fetch into a quietly halved portfolio.

## Goals / Non-Goals

**Goals:**
- Make a scrapeable-but-flaky site yield its full list consistently (retry transient blocks).
- Stop the web-search fallback from silently masking a fetch failure — surface it.
- Resolve the `web_scraper_strategy.py` 400-line ceiling so the retry can be added.

**Non-Goals:**
- Moving scraping off Lambda or onto a dedicated egress IP (bigger infra change).
- Failing the scan / SQS-retrying on persistent block (a partial web-search list beats a failed scan).
- Headless rendering (deferred); changing fallback content.

## Decisions

**1. Retry in the transport, classified by failure type.**
`fetch_page_html` retries on retryable signals (HTTP 403/408/425/429/5xx, `ConnectionError`, `Timeout`) up to a small bound (3 attempts) with brief linear backoff; 404/410 raise immediately (genuine); `ImpersonateError` raises immediately (config bug). Most intermittent Cloudflare challenges and slow-page timeouts pass on a second attempt. *Alternative — SQS-retry the whole scan on failure:* rejected; risks DLQ/failed scans on a persistent block, and an in-fetch retry already absorbs transient blips at much lower cost.

**2. Move the transport to `scraper_transport.py`.**
`web_scraper_strategy.py` is at exactly 400 lines (audit ceiling). The curl_cffi fetch + retry is a distinct concern from BeautifulSoup parsing, so it moves to `scraper_transport.py` (with `_IMPERSONATE_TARGET`, `_SCRAPER_TIMEOUT`, retry constants). `web_scraper_strategy` imports and re-exports `fetch_page_html` (so existing callers/tests that reference `web_scraper_strategy.fetch_page_html` keep working, including the `scrape_url` patch in tests). This frees ~20 lines and gives the retry a clean home.

**3. Genuine-zero vs fetch-failure, surfaced not enforced.**
The strategy records a fetch failure when a portfolio *listing* page raises a non-404 error after retries (a real block/timeout), versus genuinely returning content. It exposes this in metadata. `DiscoverPortfolio` keeps the existing fallback trigger (`site_total <= threshold`) but, when it fires, logs WARNING if the cause was a fetch failure ("results may be incomplete") vs INFO for a genuine empty site. The fallback still runs as recovery — a 75-company list beats zero — but the degradation is now diagnosable. *Alternative — suppress the fallback on fetch failure:* rejected; that would return zero on a hard block, strictly worse.

## Risks / Trade-offs

- **Retry latency** → up to 2 extra attempts × (timeout + backoff) on a hard-blocked page. Bounded (3 attempts); only on failure; discovery is async. Acceptable.
- **Retrying the large page twice more** → only when it failed; the common success path is unchanged (returns on attempt 1).
- **Module split churn** → re-export keeps `web_scraper_strategy.fetch_page_html` valid; the dedicated `TestFetchPageHtml` moves to `test_scraper_transport.py`. Mechanical, covered by tests.
- **Persistent block still degrades to 75** → by design (recovery), now logged so it is visible and actionable.

## Migration Plan

1. Create `scraper_transport.py` with `fetch_page_html` (+ retry, constants); `web_scraper_strategy` re-exports it; move/extend the transport tests.
2. Strategy: track listing-page fetch failure → metadata flag.
3. `DiscoverPortfolio`: log fallback cause (fetch-failure WARNING vs genuine-zero INFO).
4. Tests: retry-on-403-then-200, no-retry-on-404, raise-after-exhaustion; strategy flags fetch failure; discovery logs cause.
5. Full gates + architecture review + E2E; deploy via branch promotion; re-run Francisco on dev to confirm consistent full counts. Rollback = revert the PR.

## Open Questions

- Retry count/backoff defaults (start at 3 attempts / ~1.5 s linear) — tune later from CloudWatch if blocks persist.
