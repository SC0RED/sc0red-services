## 1. Deterministic embedded-company extractor

- [x] 1.1 Add `_extract_embedded_companies(soup)` to `web_scraper_strategy.py`: scan inline (non-`src`) `<script>` content for adjacent `"name":"…","slug":"…"` records, handling both plain and escaped (`\"…\"`) JSON; return `list[{"name","slug"}]` deduped by slug. Run on full script content (no `_MAX_SCRIPT_TEXT_LENGTH` cap).
- [x] 1.2 Require `name` immediately followed by `slug` so logo/asset objects and `searchableNormalized` are excluded; bound name length with the existing `MIN_NAME_LENGTH`/`MAX_NAME_LENGTH`.
- [x] 1.3 Add `embedded_companies` to the `scrape_url` return dict (additive; existing keys unchanged).

## 2. Wire structured candidates into discovery

- [x] 2.1 In `PortfolioDiscoveryStrategy.execute()`, for each scraped page read `result["embedded_companies"]` and build a candidate per record: `{"name": name, "url": f"{page_url.rstrip('/')}/{slug}"}`.
- [x] 2.2 Merge structured candidates with the heuristic-link candidates (apply the same social/CTA/length filters where appropriate, dedup by normalized URL/domain) before returning metadata.
- [x] 2.3 Confirm the candidates flow through `DiscoverPortfolio` merge → `needs_validation` (never auto-included without validation) with no change to `DiscoverPortfolio`.

## 3. Tests

- [x] 3.1 `_extract_embedded_companies`: escaped-JSON fixture (TB-shaped) → all records; plain-JSON fixture → records; logo/`searchableNormalized` noise objects excluded; no-records HTML → empty; dedup by slug.
- [x] 3.2 `scrape_url` returns `embedded_companies` (mock transport) without disturbing title/text/links/script_text.
- [x] 3.3 `PortfolioDiscoveryStrategy`: embedded records → detail-page candidate URLs (`/portfolio/{slug}`); dedup against an overlapping heuristic link; page with no embedded records unchanged.

## 4. Validation & verification

- [x] 4.1 `ruff check` + `ruff format` + naming validator + abbreviations clean on changed files
- [x] 4.2 `pyright src/` introduces no new error category
- [x] 4.3 `pytest tests/ -q` passes with coverage ≥ 95%
- [ ] 4.4 Run the `architecture-reviewer` agent; resolve CRITICAL before commit
- [x] 4.5 Reproduce the customer case: `thomabravo.com/portfolio` now yields the full embedded company list (local check), and a detail-page candidate resolves to the real company site
- [ ] 4.6 Run the E2E suite per CLAUDE.md before opening the PR

## 5. Documented next step (do NOT implement here)

- [x] 5.1 Record in design.md that detail-path derivation defaults to `{listing_page}/{slug}` and that inferring a different prefix is deferred until real data shows a firm nesting detail pages elsewhere
