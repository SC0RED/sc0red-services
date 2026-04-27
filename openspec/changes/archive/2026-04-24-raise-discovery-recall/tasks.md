## 1. Remove the heuristic company-count cap

- [x] 1.1 Delete the `_MAX_COMPANIES = 30` constant and its two usage sites (`if len(companies) >= _MAX_COMPANIES: break` in the main loop and in the `_fallback_data_attributes` path) in `backend/src/data_strategies/portfolio_discovery_strategy.py`
- [x] 1.2 Add a regression test in `backend/tests/unit/data_strategies/test_portfolio_discovery.py` that feeds a synthetic page with 50 external portfolio anchors and asserts the heuristic returns all 50 (not 30)

## 2. Improve name derivation — img src filename fallback

- [x] 2.1 Add a helper `_name_from_img_src(src: str) -> str` to `backend/src/data_strategies/web_scraper_strategy.py` that:
  - extracts the basename (no path, no extension)
  - strips common suffixes (`-logo`, `_logo`, trailing `logo`)
  - splits on `-`, `_`, and camelCase boundaries
  - title-cases the result
- [x] 2.2 Modify `_extract_context_name` in the same file: when `<img alt>` is missing or empty, call `_name_from_img_src(img['src'])` as the next fallback before breaking out of the walk
- [x] 2.3 Unit tests for `_name_from_img_src`: cover `accesshealthcare.png`, `access-healthcare.png`, `access_healthcare.png`, `accessHealthcare.png`, `fold-health-logo.png`, full URL input, edge cases (empty, query string, no extension)
- [x] 2.4 Fixture test: `TestExtractContextNameImgSrcFallback` replicates the perotjain `<article class="single-card"><div class="overlay-content"><img alt="" src="...logo.png"><a>LEARN MORE</a></div></article>` pattern exactly — covers the 9 failing cards structurally without checking in 79KB of third-party HTML

## 3. Improve name derivation — URL-domain fallback

- [x] 3.1 Add a helper `_name_from_url(url: str) -> str` to the same module — parse hostname, strip `www.`, drop TLD, apply the same title-casing pipeline
- [x] 3.2 In `portfolio_discovery_strategy.py` main loop, after the existing `is_generic_cta or not text` branch fails to produce a name, call `_name_from_url(full_url)` as the last resort rather than dropping the candidate
- [x] 3.3 Unit tests for `_name_from_url`: `endurancelift.com`, `www.endurancelift.com`, `https://www.endurancelift.com/path`, hyphenated domains, subdomains

## 4. Raise AI-extraction truncation limits

- [x] 4.1 Update `backend/src/pipeline/pipeline_steps/discover_portfolio.py` — in `_run_ai_extraction`, change `page_text[:8000]` → `page_text[:30000]`, `links_text[:3000]` → `links_text[:10000]`, `links[:100]` → `links[:300]`
- [x] 4.2 Extract the three numeric limits as module-level constants (`_AI_PAGE_TEXT_BUDGET`, `_AI_LINKS_TEXT_BUDGET`, `_AI_LINK_COUNT_BUDGET`) so future tuning is a one-line change
- [x] 4.3 Confirmed no existing tests assert the old truncation constants; new values live as module constants so any future test can import and reference them. Actual truncation behavior is exercised indirectly by existing `test_discover_portfolio.py` tests running the full AI extraction path — confirmed post-change via the full test run.

## 5. DynamoDB / downstream safety check

- [x] 5.1 DynamoDB item limit is 400KB; 300 companies × ~200 bytes each = ~60KB via `json.dumps(portfolio_companies)` in `scan_repository.py:37`. Well under cap; no test needed.
- [x] 5.2 `_compute_scan_progress` iterates `analyses` once (O(N)) with a summation — linear, no quadratic risk at any realistic N. `_derive_progress_label` uses a single `max()` pass. Both safe for 300+ entries.

## 6. Quality gates

- [x] 6.1 `cd backend && uv run ruff check src/ && uv run ruff format --check src/` — clean
- [x] 6.2 `cd backend && uv run pyright src/` — back to baseline 33 errors on the three modified files (zero new)
- [x] 6.3 `cd backend && uv run pytest tests/ -q` — 723 tests pass; 75 targeted re-runs after review fixes pass
- [x] 6.4 Architecture-reviewer agent — MEDIUM (stale pyright suppression) and LOW (`except ValueError`, duplicate constants, test comment) findings all resolved
- [x] 6.5 Frontend: 392 tests pass — confirmed earlier

## 7. Deploy + verify

- [x] 7.1 Open PR against `development`; CI green (PR #157 — merged)
- [x] 7.2 Deployed to `development` AWS account via CI
- [x] 7.3 Manual smoke: perotjain.com scan in dev UI — recall lifted from 35-38 to 60+ companies post-validation
- [x] 7.4 Token spend for the perotjain scan reviewed via CloudWatch AI-call logs — cost impact within the expected 2-3× envelope; no rollback required in 8+ days of production use
- [x] 7.5 Promoted `development` → `testing` → `production`
