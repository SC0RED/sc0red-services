## Why

Portfolio discovery is non-deterministic for Francisco Partners: two scans 13 minutes apart (same firm, same deployed code) returned 175 and 75 companies. Root-caused on `development`: the 175 are the site-scrape heuristic (`franciscopartners.com/investments/{slug}`), the 75 are the **web-search fallback** (external "current notable" URLs). The fallback only fires when the worker's site scrape yields ~0. Scraping from a normal IP is rock-solid (6/6), so the worker's fetch of the large 835 KB `/investments` page intermittently fails — a Lambda datacenter egress IP gets challenged by Cloudflare more aggressively (even with the TLS impersonation), and/or the page occasionally trips the 15 s timeout. A single failed fetch silently degrades discovery from the authoritative full list to a smaller web-search subset, with no signal that it happened.

## What Changes

- **Retry the fetch** in the scraping transport: on a transient/blocked response (HTTP 403/408/429/5xx, connection error, timeout) retry a few times with brief backoff before giving up. Genuine not-found responses (404/410) are NOT retried. This absorbs the intermittent Cloudflare challenge / slow-page failures so a scrapeable site yields its full list consistently.
- **Fall back only on a genuine zero, surfaced otherwise**: the discovery strategy distinguishes "the listing page genuinely returned content but no companies" from "the listing fetch failed (blocked/timed out after retries)". When the web-search fallback fires after a fetch *failure*, log it at WARNING with the cause, rather than silently presenting a smaller list as the answer. The fallback remains the recovery path (a partial list beats zero), but the degradation is now observable.
- **Split the scraping transport into its own module** (`scraper_transport.py`) — `web_scraper_strategy.py` is at the 400-line audit ceiling, and the retry logic belongs with the transport, not the BeautifulSoup parsing.

## Capabilities

### New Capabilities
- `scrape-retry-resilience`: the scraping transport retries transient/blocked fetches before failing, and portfolio discovery distinguishes a genuine empty site from a fetch failure so the web-search fallback no longer silently masks intermittent scrape blocks.

### Modified Capabilities
<!-- Behavior strengthening within the existing scrape transport + discovery flow; no spec-level requirement of another capability changes. -->

## Impact

- **Code:** new `src/data_strategies/scraper_transport.py` (moves `fetch_page_html` + impersonation/timeout constants from `web_scraper_strategy.py`, adds retry); `web_scraper_strategy.py` imports/re-exports `fetch_page_html` (drops ~20 lines, resolving the 400-line ceiling); `portfolio_discovery_strategy.py` tracks listing-page fetch failures; `discover_portfolio.py` logs fallback cause (fetch-failure vs genuine-zero).
- **Behavior:** scrapeable-but-flaky sites (Francisco, Thoma Bravo) return their full lists consistently instead of intermittently dropping to the web-search subset; truly opaque sites (Vista) still get the fallback; degraded runs are now logged, not silent.
- **Out of scope:** moving discovery off Lambda / dedicated scraping egress (a larger infra change); headless rendering (deferred); changing the web-search fallback content.
