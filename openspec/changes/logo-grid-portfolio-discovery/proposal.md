## Why

Vista Equity Partners (`vistaequitypartners.com`) shows only ~2 portfolio companies, though it holds ~68. Diagnosed on `development`: Vista renders its portfolio as a **grid of logo images** with the company name only in `<img alt="Logo of software company Jamf">` — the logos are **not links**, there are **no per-company detail pages** (all 404), and there are **no company URLs anywhere on the page**. Our scraper reads nothing from this (alt text is neither body text, an `<a>` link, nor a JSON island), so the site path yields 0 and the AI sees zero portfolio names. The web-search fallback then fires (as designed for opaque sites) but its prompt is over-conservative ("CURRENT notable… favour companies you are confident… do not include exited") with no breadth target, so it returns only a couple. The firm's authoritative list is right there on the page — we just don't read logo-alt grids, and we don't use that list to drive the URL lookup.

## What Changes

- Add **logo-grid name extraction**: read company names from logo `<img alt>` text (patterns like "Logo of [software] company {Name}" and "{Name} logo"), cleaned, the firm's own logo excluded, length-bounded, deduped. Surfaced as a new `logo_company_names` field from `scrape_url` and threaded through `PortfolioDiscoveryStrategy` metadata.
- **Seed the web-search fallback** with those on-site names: when the site path yields nothing but logo-grid names exist, pass them into a single grounded web-search call that returns each company's official website URL (plus any other current holdings it finds). The site supplies the authoritative WHO; web search supplies the URLs — one grounded call, not one per company.
- **Broaden the fallback prompt** for the unseeded (truly opaque, no logo grid) case: request comprehensive current holdings rather than a timid shortlist.
- Fallback results stay in the `needs_validation` tier (AI-validated, then scanned), unchanged. The trigger threshold is unchanged (fires only when the site path yields nothing).

## Capabilities

### New Capabilities
- `logo-grid-portfolio-discovery`: discover portfolio companies on logo-grid sites by extracting company names from logo image `alt` text, and resolve their official URLs by seeding the grounded web-search fallback with those names.

### Modified Capabilities
<!-- The web-search fallback shipped in resilient-portfolio-discovery (not yet archived), so its behavior change (seeding + breadth) is captured here under the new capability rather than as a delta to a live spec. -->

## Impact

- **Code:** `src/data_strategies/web_scraper_strategy.py` (new `_extract_logo_companies`; `scrape_url` returns `logo_company_names`), `src/data_strategies/portfolio_discovery_strategy.py` (collect `logo_company_names` into metadata), `src/pipeline/pipeline_steps/discover_portfolio.py` (`_run_web_search_fallback` accepts seed names; pass them from `execute`).
- **Prompts:** `src/pipeline/prompts/templates/discover_portfolio_websearch.md` — breadth + optional known-companies seed list.
- **Behavior:** logo-grid sites (Vista and similar) recover their full current portfolio with resolved URLs; opaque sites get broader web-search recall. Embedded-JSON (Thoma Bravo) and anchor-link sites are unaffected (the fallback only fires when the site path yields nothing).
- **Out of scope:** guessing company URLs from names without web search; per-company grounded calls; scraping headless-only sites with neither logos nor embedded data (Playwright remains the deferred escalation).
