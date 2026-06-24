# Design — Harden the scraper against SSRF

## Chokepoint

All server-side scrapes bottom out at `fetch_page_html` in
`scraper_transport.py`:

```text
scan/start → DiscoverPortfolio → PortfolioDiscoveryStrategy ─┐
scan/{id}/source-url → FetchProvidedSource ─────────────────┼─→ scrape_url ─→ fetch_page_html ─→ curl_requests.get
single-scan → scrape_and_resolve → scrape_url ──────────────┘                 (also called directly by
                                                                                portfolio_discovery_strategy)
```

Enforcing the guard in `fetch_page_html` covers every entry point with one
check — no per-handler patching, no risk of a new entry point bypassing it.
(`/scan/{id}/deepen` is web-search-based and never fetches the URL itself, so it
isn't in scope here.)

## The guard — `data_strategies/url_safety.py`

`assert_public_url(url)` raises `UnsafeUrlError(ValueError)` when:

1. scheme ∉ {`http`, `https`}, or the URL has no host;
2. (unless the escape hatch is set) the host resolves — via
   `socket.getaddrinfo` over **all** returned A/AAAA records — to any IP that is
   `is_private | is_loopback | is_link_local | is_multicast | is_reserved |
   is_unspecified`. IPv4-mapped IPv6 (`::ffff:a.b.c.d`) is unwrapped first so it
   can't smuggle a blocked v4. A resolution failure is itself a rejection.

Checking **every** resolved record (not just the first) blocks the trick of a
hostname with both a public and a private A record.

### Escape hatch

`SCRAPER_ALLOW_PRIVATE_HOSTS` (truthy → skip the IP checks; scheme/host checks
still apply). Off by default, so production Lambda is guarded without config.
Set to `true` only in `docker-compose.e2e.yml` (and ad-hoc local stacks) where
the scan target is the internal `ai-mock` host on a private docker address.

## Redirects

`curl_cffi` followed redirects automatically (`allow_redirects=True`), which
would let `https://evil.example/` 302 → `http://169.254.169.254/`. So:

- `fetch_page_html` becomes a manual redirect loop (max `_MAX_REDIRECTS = 5`).
- Each hop: `assert_public_url(current)` → fetch with `allow_redirects=False`
  (retry logic extracted to `_fetch_once`, which returns the `Response`) → if
  3xx with a `Location`, resolve it against the current URL and re-loop; else
  return the body.
- Exceeding the redirect cap raises `UnsafeUrlError`.

The retry/backoff/impersonation behaviour is preserved exactly — only the
redirect following moves from libcurl into our loop so each hop is validated.

## Residual risk (documented, out of scope)

A DNS-rebinding TOCTOU remains: `getaddrinfo` validates, then libcurl resolves
again at connect time, so a hostname that flips its record between the two could
slip a private IP through. Fully closing it needs per-request resolve-pinning,
which `curl_cffi.requests.get` does not expose. The direct attacks (literal
private IPs, `localhost`, metadata IPs, redirect-to-private) are all blocked;
the rebinding window is narrow and noted for a future transport change.

## Error contract

`UnsafeUrlError` subclasses `ValueError`, and a malformed-port `ValueError` from
`urlparse` is normalised to `UnsafeUrlError` so the whole refusal surface is one
exception type. Consumers then choose their response explicitly:

- The discovery strategy treats a refusal as an **unreachable site** —
  fail-soft: the main scrape loop sets `site_fetch_failed=True` (→ `site_blocked`
  verdict) and the speculative fallback skips the path; `scrape_and_resolve`
  degrades to the original content. This matches how those paths already handle
  `RequestException`, so an internal/blocked URL behaves like any unreachable one
  rather than crashing the scan.
- Anything that does NOT catch it (e.g. a future direct caller) still fails
  loudly via the worker's `except (EngineError, ValueError, RuntimeError)`, which
  records a clean failure. No silent pass — a blocked URL is never fetched.

## Tests

- `test_url_safety.py`: literal `127.0.0.1`, `10.x`, `169.254.169.254`, `::1`,
  IPv4-mapped, `0.0.0.0`, multicast, reserved → rejected; `file://`/`ftp://` →
  rejected; unresolvable host → rejected; a mocked-public resolution → allowed;
  escape-hatch env → private allowed. `getaddrinfo` is mocked (no real DNS).
- `test_scraper_transport.py`: guard mocked in the existing retry tests
  (kept network-free); new tests for redirect-to-public (followed) and
  redirect-to-private (rejected), and the redirect cap.
