# Harden the server-side scraper against SSRF

## Why

Every server-side page fetch funnels through `fetch_page_html`
(`backend/src/data_strategies/scraper_transport.py`), which `curl_cffi`-GETs
whatever URL it's handed with `allow_redirects=True` and **no IP/host filtering**.
Three entry points feed it attacker-controllable URLs:

- `POST /api/scan/start` — arbitrary `url`
- `POST /api/scan/{id}/source-url` — the customer-provided page URL (PR #435)
- (the discovery/analysis pipelines that scrape those URLs downstream)

So a customer can make the worker issue requests to `http://169.254.169.254/…`
(cloud metadata), `http://localhost`, or any private/loopback/link-local host —
a classic SSRF. CodeRabbit flagged this **Critical** on PR #435; it was deferred
there because the fix is product-wide (the scraper layer), not endpoint-specific.

## What changes

- A shared guard, `assert_public_url(url)`, enforced **inside `fetch_page_html`**
  so all entry points are covered at the single network chokepoint.
- The guard rejects non-`http(s)` schemes and any host that resolves to a
  private, loopback, link-local, multicast, reserved, or unspecified IP
  (IPv4 and IPv6, including IPv4-mapped IPv6).
- Redirects are validated per hop: `fetch_page_html` stops auto-following and
  follows manually, re-running the guard on each `Location` so an allowed host
  can't 30x-redirect into a blocked range.
- An env escape hatch, `SCRAPER_ALLOW_PRIVATE_HOSTS`, disables the IP checks for
  the E2E / local docker stacks (which scrape an internal `ai-mock` host). It is
  **off by default**, so production (Lambda) is guarded with no extra config.

## Impact

- Affected code: `scraper_transport.fetch_page_html`; new
  `data_strategies/url_safety.py`; `docker-compose.e2e.yml` env.
- Affected specs: new `scraper-url-safety` capability.
- Behaviour: blocked URLs raise `UnsafeUrlError` (a `ValueError`), which the
  worker's domain-error handling surfaces as a clean failure (not a 500/crash).
  Legitimate public scrapes are unchanged. No API contract change.
- Out of scope: full DNS-rebinding TOCTOU pinning (curl_cffi has no per-request
  resolve-pin hook); an allowlist beyond the test escape hatch; HTTPS-only
  enforcement (the product legitimately scrapes http sites).
