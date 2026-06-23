# Phase 1 — Confidence-aware dedup (smallest, highest-reliability; could land before the current epic archives)

- [x] 1.1 Replace URL-only dedup in `portfolio_merge.merge_fallback` and `DeepenPortfolio` with confidence-aware dedup: seed the `seen` set with the trusted set's normalized **names** AND url-keys; drop a web-search candidate matching either. Trusted entry always wins.
- [x] 1.2 Add `_normalize_company_name` (lowercase, strip suffixes Inc/LLC/Ltd/Corp/Co/GmbH/SA, collapse punctuation/whitespace) to `portfolio_merge` (shared, with a noqa if the naming checker balks).
- [x] 1.3 Tests: site `Acme(acme.com)` suppresses web-search `Acme(acme.in)`; web-search TLD dupes collapse; distinct names preserved; a trusted company is never dropped.

# Phase 2 — Provenance + confidence (backend → UI)

- [x] 2.1 Add `source` to each candidate (`site`/`web_search`/`upload`/`provided_url`) through the merge in `DiscoverPortfolio`/`DeepenPortfolio`; capture the scraped firm page URL in strategy metadata and carry it onto the verdict as `site_source_url`. Persist; expose via scan read API (camelCase) + MCP.
- [x] 2.2 Frontend: `DiscoveryVerdictBanner`/confirm screen group reliable (site/upload/provided_url) vs best-effort (web_search), show the site source line, reuse `ProvenanceMarker` (`from-scrape`/`from-upload`). Web-search rows unchecked + "verify" subhead + unverified-URL flag; reliable rows pre-selected.
- [x] 2.3 Tests: backend source-tagging + verdict source counts; frontend grouping/pre-selection/badges.

# Phase 3 — Honest incompleteness messaging

- [x] 3.1 Enrich the verdict with a reliability `reason` from existing signals (big script_text + tiny page_text ⇒ dynamic; site_fetch_failed ⇒ blocked); reliable-first message copy (lead with "read N from <firm page>").
- [x] 3.2 Remove/avoid any "cross-origin" phrasing; client-side-rendering described as "builds its list in the browser after load". Backend (MCP) + frontend copy.
- [x] 3.3 Tests: message per reason; no false cross-origin claim.

# Phase 4 — Provide-a-reliable-URL correction path

- [x] 4.1 `scan_core` entry (mirror deepen/upload) that fetches a customer-provided URL server-side via the existing scraper + extraction → `provided_url` candidates, merged trusted-wins. Worker + message + `POST /api/scan/{id}/source-url`. (`FetchProvidedSource` step, `PortfolioSourceUrlFactory`, `build_portfolio_source_url_message`, shared `_process_additive_merge` worker path, `scan_core.fetch_source_url`, `handle_scan_source_url` route. `extract_companies_from_scrape` extracted from `DiscoverPortfolio` for reuse — no web-search fallback so the provided source stays reliable.) MCP option deferred.
- [ ] 4.2 Frontend "Paste a page URL" affordance beside Upload; expectation-setting if the provided page is CSR / unreachable.
- [x] 4.3 Tests (backend): provided URL merges high-confidence `provided_url`; a page that adds nothing new leaves the scan's prior verdict + list intact (no relabelling to site-derived); fetch failure restores prior list; dedup against seed; heuristic-only (no-AI) path; route 202/400/404.

# Validation (each phase)

- [ ] V.1 ruff + ruff format + naming + abbreviations (backend); npm lint + tsc (frontend)
- [ ] V.2 pytest ≥95% + frontend vitest; architecture-reviewer; E2E before PR
- [ ] V.3 per-phase PR; branch → PR → await merge authorization

# Notes / deferred

- Power-user lever (NOT built here): a CSR firm fetches its portfolio from its own JSON endpoint (e.g. `firm.com/api/portfolio`); fetching that server-side is the most reliable+complete path. Surfaced in design as future, too technical for end users now.
- Playwright render rung remains deferred to its own change.
