# Tasks — Harden the scraper against SSRF

- [x] 1. `data_strategies/url_safety.py`: `UnsafeUrlError(ValueError)` +
  `assert_public_url(url)` (scheme + getaddrinfo over all records, block
  private/loopback/link-local/multicast/reserved/unspecified, unwrap
  IPv4-mapped IPv6, reject unresolvable). Env opt-out `SCRAPER_ALLOW_PRIVATE_HOSTS`.
- [x] 2. `scraper_transport.fetch_page_html`: validate up front; extract the
  retry loop to `_fetch_once` (returns `Response`, `allow_redirects=False`);
  manual redirect loop (`_MAX_REDIRECTS`) re-validating each hop.
- [x] 3. `docker-compose.e2e.yml`: set `SCRAPER_ALLOW_PRIVATE_HOSTS: "true"` in
  the shared env so the `ai-mock` scrape target is reachable in E2E.
- [x] 4. Tests: `test_url_safety.py` (blocked ranges, ipv4-mapped, schemes,
  unresolvable, public-allowed, env opt-out — getaddrinfo mocked); update
  `test_scraper_transport.py` (mock the guard in retry tests; add
  redirect-to-public, redirect-to-private, redirect-cap).
- [x] 4b. Consumers treat `UnsafeUrlError` (a `ValueError`) as a fail-soft
  unreachable site, not a crash: `portfolio_discovery_strategy` main loop
  (`site_fetch_failed=True`) + speculative fallback (skip path), and
  `scrape_and_resolve` resolved-URL scrape (degrade to original). Tests for each.
- [x] 5. Validation: ruff + ruff format + naming + pyright; pytest ≥95%;
  architecture-reviewer (0 CRITICAL; 1 MEDIUM + 2 LOW all resolved).
- [ ] 6. E2E before PR; branch → PR → await merge authorization.
