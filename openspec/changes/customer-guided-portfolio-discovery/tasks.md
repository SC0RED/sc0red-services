# Phase 1 — Verdict + messaging + CSV/PDF upload (this change's implementable scope)

## 1. Discovery verdict

- [x] 1.1 In `DiscoverPortfolio`, build a `discovery_verdict` dict: `method` (site/web_search/upload), `count`, `completeness` (full_site_list / site_blocked / web_search_subset / genuinely_empty), `available_actions` (subset of search_deeper, render_site, upload_list). Derive from existing signals: which path produced candidates and `site_fetch_failed` (#425). (A CSR firm maps to web_search_subset — not a separate value.)
- [x] 1.2 Persist the verdict on the scan record in the worker (alongside `portfolio_companies`, `status=awaiting_confirmation`); expose it via the scan read API + MCP `get_scan`.
- [x] 1.3 Unit tests: verdict for CSR-thin (web_search_subset + search_deeper/upload), full-site (full_site_list), blocked (site_blocked), genuine-empty.

## 2. Customer-facing message + action affordances (frontend)

- [x] 2.1 Confirmation screen renders the verdict as a plain-language message (cause + count) via `DiscoveryVerdictBanner`, keyed on `completeness`; falls back to the original "discovered N" banner for verdict-less (legacy) scans. The HTTP scan-status response now carries `discoveryVerdict` (camelCase mapping in `scan_handlers._verdict_response`), threaded through `useScanPolling`/realtime/direct paths into page state.
- [x] 2.2 Renders `availableActions` as explicit choices. Only `upload_list` is live in Phase 1 (reveals the uploader); `search_deeper`/`render_site` are surfaced as disabled "soon" affordances (their backends are Phase 2/3). A `full_site_list` verdict shows a positive message and only the upload action.
- [x] 2.3 Frontend tests: message rendering per completeness, action enable/disable, upload-widget reveal, verdict forwarding through the polling hook.

## 3. CSV/PDF company-list upload

- [x] 3.1 Backend: parse an uploaded CSV (required `name`, optional `url`) and PDF/text (best-effort names via `src/documents/extract_text.py`) into `{name, url}` candidates in `src/documents/parse_company_list.py` — header-aware CSV, bare-domain → https normalization, dedup by name. `url` left "" when the source omits it (customer resolves it on the confirmation screen; AI URL-resolution is a later slice).
- [x] 3.2 Stateless parse endpoint `POST /api/portfolio/parse-company-list` (`src/handlers/company_list_handlers.py`) — reuses the existing base64 upload transport, returns candidates + counts (`withUrl`/`needsUrl`). Chosen over a new `scan_core` dispatch entry: the parsed list flows into the editable confirmation list and scans through the **existing** confirm path, so no new scan-start surface or worker change is needed. Frontend uploader (`CompanyListUpload`) wired in the confirmation screen, gated behind the verdict's "Upload a list" action, bulk-merging into the editable list with URL/name dedup. (MCP paste-list reuse remains a later option.)
- [x] 3.3 Tests: CSV name+url; CSV name-only (url ""); alternate headers; no-header rows; ragged rows; PDF/text best-effort + inline-url; dedup; max-cap; malformed/unsupported/empty handled gracefully; handler success + 400 paths.

## 4. Validation & verification (Phase 1)

- [x] 4.1 `ruff` + `ruff format` + naming + abbreviations clean (backend); `npm run lint` + `tsc` (frontend)
- [x] 4.2 `pyright src/` no new error category
- [x] 4.3 `pytest tests/ -q` ≥ 95% coverage; `cd frontend && npm test` passes
- [x] 4.4 Run the `architecture-reviewer` agent; resolve CRITICAL before commit
- [ ] 4.5 E2E suite per CLAUDE.md before the PR (extend the mock if the verdict/upload path is exercised)

# Phase 2 — Deeper web-search rung (follow-on; own PR)

- [x] 5.1 Multi-pass deeper web search (`portfolio_websearch.run_deep_web_search_discovery`: 3 angled, seeded passes, deduped) driven by a new `DeepenPortfolio` step + `PortfolioDeepenFactory`, routed via `factories_factory` (`request_type="portfolio_deepen"`, seed in `event.extra`). `scan_core.deepen_scan` + worker `_process_portfolio_deepen` (seeds from the scan's current list, merges new candidates via the existing `ValidatePortfolioCompanies`, rebuilds the verdict; a deepen failure restores the prior list rather than failing the scan). Merge/verdict + web-search helpers extracted to shared `portfolio_merge` / `portfolio_websearch` modules (also drops `discover_portfolio.py` 393→218 lines, no behavior change).
- [x] 5.2 (backend) `POST /api/scan/{scan_id}/deepen` (`scan_handlers.handle_scan_deepen`; 404 wrong-org, 400 unless awaiting_confirmation). Backend tests cover the step, multi-pass dedup/seeding, factory routing, worker (dispatch/success/restore-on-failure/propagate), message, and route. **Frontend wiring of the "Search deeper" button + E2E are the next slice** (the button currently renders as a disabled "soon" affordance from Phase 1).

# Phase 3 — Headless render rung (DEFERRED — separate change)

- [ ] 6.1 Do NOT implement here. `render_site` is surfaced as an opt-in action; until the engine exists, selecting it tells the customer it is not yet available and points to deeper-search/upload. The Playwright (chromium-in-Lambda) engine is its own change with its own infra review.

# Phase 4 — Verdict-completeness correction + deepen exhaustion (dev-verification findings, 2026-06-22)

Found while verifying Phases 1+2 on dev: partial scrapes (Audax 4, Alpine 3, GA 19…) are mislabeled `full_site_list`, which hides "Search deeper" and falsely claims completeness; and deepen can't signal exhaustion so we can't honestly redirect to upload. See design.md "Correction" (decisions 6–8).

- [x] 7.1 `build_verdict`: stop inferring completeness from a non-zero count. Add `partial_site_list` (non-zero-but-uncertain) — message conveys the list may be incomplete. `available_actions` ALWAYS includes `upload_list`, and includes `search_deeper` for every completeness except `full_site_list`. Reserve `full_site_list` for results with a positive completeness signal (default uncertain non-zero → `partial_site_list`).
- [x] 7.2 Raise the thin-scrape auto-fallback gate: run the web-search fallback when `site_total` is below a small low-water mark (not only `== 0`), so clearly-broken scrapes (≤ a few) auto-augment; tune N conservatively from real data. Keep expensive work customer-gated otherwise.
- [x] 7.3 Deepen exhaustion: thread `added_this_round` out of `DeepenPortfolio` into the verdict; converge (loop angled passes until a round adds nothing new, safety-capped, OR detect a zero-delta round); add `web_search_exhausted` completeness whose message states no more were found and directs to upload, and stop presenting search-deeper as productive.
- [x] 7.4 Frontend: render `partial_site_list` and `web_search_exhausted` messages in `DiscoveryVerdictBanner`; surface "added N" after a deepen; when exhausted, point to Upload and de-emphasize/disable Search deeper.
- [x] 7.5 Honesty: messaging makes clear web search is recall, not enumeration — upload is the only complete path. Update existing `web_search_subset`/`full_site_list` copy if it over-claims.
- [x] 7.6 Tests: verdict matrix (partial vs full vs exhausted; actions always include escalation except full); deepen added-count + exhaustion convergence; frontend banner per new completeness. E2E.
- [ ] 7.7 Open (needs AI key / dev MCP): confirm whether Insight's 147 KB JSON island yields the full portfolio or a page — determines whether Insight is genuinely `full_site_list` or `partial_site_list`. Does not block 7.1 (always-offer-escalation is correct either way).
