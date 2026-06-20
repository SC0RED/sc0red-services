# Phase 1 — Verdict + messaging + CSV/PDF upload (this change's implementable scope)

## 1. Discovery verdict

- [x] 1.1 In `DiscoverPortfolio`, build a `discovery_verdict` dict: `method` (site/web_search/upload), `count`, `completeness` (full_site_list / site_blocked / web_search_subset / genuinely_empty), `available_actions` (subset of search_deeper, render_site, upload_list). Derive from existing signals: which path produced candidates and `site_fetch_failed` (#425). (A CSR firm maps to web_search_subset — not a separate value.)
- [x] 1.2 Persist the verdict on the scan record in the worker (alongside `portfolio_companies`, `status=awaiting_confirmation`); expose it via the scan read API + MCP `get_scan`.
- [x] 1.3 Unit tests: verdict for CSR-thin (web_search_subset + search_deeper/upload), full-site (full_site_list), blocked (site_blocked), genuine-empty.

## 2. Customer-facing message + action affordances (frontend)

- [ ] 2.1 Confirmation screen renders the verdict as a plain-language message (cause + count) instead of a bare number.
- [ ] 2.2 Render `available_actions` as explicit choices (Search deeper / Render the site / Upload a list) alongside a primary "Proceed with these N"; actions shown contextually (only when the result looks incomplete).
- [ ] 2.3 Frontend tests: message rendering per completeness; actions appear/disappear correctly.

## 3. CSV/PDF company-list upload

- [ ] 3.1 Backend: parse an uploaded CSV (required `name`, optional `url`) and PDF (best-effort names via `src/documents/extract_text.py`) into `{name, url?}` candidates; feed into the existing validation → per-company scan path (resolve URL when absent); merge/dedup with any existing candidates.
- [ ] 3.2 Wire an upload entry through `scan_core` (same dispatch for UI + MCP); reuse the existing document-upload UI from the report-data-integrity work.
- [ ] 3.3 Tests: CSV name+url; CSV name-only (URL resolved downstream); PDF best-effort; merge/dedup with discovery candidates; malformed file handled gracefully.

## 4. Validation & verification (Phase 1)

- [x] 4.1 `ruff` + `ruff format` + naming + abbreviations clean (backend); `npm run lint` + `tsc` (frontend)
- [x] 4.2 `pyright src/` no new error category
- [x] 4.3 `pytest tests/ -q` ≥ 95% coverage; `cd frontend && npm test` passes
- [x] 4.4 Run the `architecture-reviewer` agent; resolve CRITICAL before commit
- [ ] 4.5 E2E suite per CLAUDE.md before the PR (extend the mock if the verdict/upload path is exercised)

# Phase 2 — Deeper web-search rung (follow-on; own PR)

- [ ] 5.1 Add a "deeper" web-search mode (broader target / multi-pass) to the fallback; wire `scan_core` escalate entry (`deepen_scan(scan_id, tier="search_deeper")`) that re-runs discovery and merges/dedups into the existing set, returning an updated verdict.
- [ ] 5.2 "Search deeper" action triggers it; tests + E2E.

# Phase 3 — Headless render rung (DEFERRED — separate change)

- [ ] 6.1 Do NOT implement here. `render_site` is surfaced as an opt-in action; until the engine exists, selecting it tells the customer it is not yet available and points to deeper-search/upload. The Playwright (chromium-in-Lambda) engine is its own change with its own infra review.
