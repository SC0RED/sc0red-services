## 1. Logo-grid name extraction

- [x] 1.1 Add `_extract_logo_companies(soup)` to `web_scraper_strategy.py`: match logo `<img alt>` patterns ("Logo of [the] [software] company {Name}", "{Name} logo"), strip boilerplate/punctuation, bound by `MIN_NAME_LENGTH`/`MAX_NAME_LENGTH`, exclude the firm's own logo, dedup case-insensitively. Run before script/clutter stripping.
- [x] 1.2 Add `logo_company_names: list[str]` to the `scrape_url` return dict (additive; existing keys unchanged).
- [x] 1.3 Thread `logo_company_names` through `PortfolioDiscoveryStrategy.execute()` metadata (union across scraped pages, deduped).

## 2. Seed + broaden the web-search fallback

- [x] 2.1 Update `discover_portfolio_websearch.md`: comprehensive current-holdings framing; add an optional known-companies block ("the firm's portfolio companies include: … — return each company's official website URL, and add any other current holdings").
- [x] 2.2 `_run_web_search_fallback(firm_url, seed_names)`: render the seeded block when `seed_names` is non-empty, else the comprehensive-discovery prompt; schema unchanged.
- [x] 2.3 In `execute()`, pass `metadata.get("logo_company_names", [])` as seeds to the fallback. Fallback trigger unchanged (fires only when `site_total <= _FALLBACK_THRESHOLD`); logo names are NOT counted as site companies.

## 3. Tests

- [x] 3.1 `_extract_logo_companies`: "Logo of software company Jamf" → "Jamf"; "{Name} logo" form; firm-own logo excluded; punctuation/length cleanup; no-logo page → empty; dedup.
- [x] 3.2 `scrape_url` returns `logo_company_names` without disturbing other keys.
- [x] 3.3 `_run_web_search_fallback`: seeded prompt includes the names; unseeded prompt is the comprehensive variant (mock `run_grounded_ai_call`, assert prompt content + returned candidates).
- [x] 3.4 `DiscoverPortfolio.execute`: site path 0 + logo names → fallback seeded; healthy site → fallback not fired; logo names not double-counted as companies.

## 4. Validation & verification

- [x] 4.1 `ruff check` + `ruff format` + naming validator + abbreviations clean on changed files
- [x] 4.2 `pyright src/` introduces no new error category
- [x] 4.3 `pytest tests/ -q` passes with coverage ≥ 95%
- [ ] 4.4 Run the `architecture-reviewer` agent; resolve CRITICAL before commit
- [x] 4.5 Reproduce locally: `vistaequitypartners.com/companies` now yields ~68 logo-grid names that seed the fallback (extraction verified live; the grounded resolution itself runs in the deployed env)
- [ ] 4.6 Run the E2E suite per CLAUDE.md before opening the PR

## 5. Documented next step (do NOT implement here)

- [x] 5.1 Record in design.md that headless rendering (Playwright) remains the deferred escalation for sites with neither logos, embedded JSON, nor anchor links.
