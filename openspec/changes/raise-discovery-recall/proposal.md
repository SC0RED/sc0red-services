## Why

Portfolio discovery finds only ~35-38 companies on perotjain.com when the real portfolio page lists 70+. Empirical analysis of the raw HTML confirms:

- `_MAX_COMPANIES = 30` in `portfolio_discovery_strategy.py:51` hard-truncates the heuristic path at 30 companies regardless of page content. This was a cost-containment cap from before the "validate-only-remainder" optimization (#152) and the async SQS worker (#153) — both of which changed the cost and latency profile. The cap is load-bearing in a regime that no longer exists.
- `_extract_context_name` in `web_scraper_strategy.py` walks up the DOM looking for headings or `<img alt>` to name CTA links. On WordPress sites where logo `<img>` tags have empty `alt` attributes (very common — perotjain has 9 such cards), the function finds the empty `alt`, returns "", breaks out of the walk, and never tries the next lever. The company name is in the filename (`endurancelift.png`) but we never look there.
- When no name is derivable from HTML at all, we drop the link entirely — even though the company URL is a perfectly reasonable fallback for the name (`endurancelift.com` → "Endurance Lift").
- The AI extraction path truncates `page_text[:8000]` and sends only the first 100 links in `links_text[:3000]`. On a page with 70 portfolio rows each with a description, 8000 characters covers maybe half the page.

Together these turn a 70-company page into a 35-company result. The user impact: PE firms doing diligence see ~half their portfolio. They either abandon the tool or manually type in the missing companies.

## What Changes

- **Remove `_MAX_COMPANIES = 30` cap** in `portfolio_discovery_strategy.py`. Rely on the async SQS worker's 15-minute budget and the AI validation step to filter false positives. Expected effect: perotjain recall jumps from ~35 to ~60+.
- **Add img-src-filename fallback** to `_extract_context_name`: when `<img alt>` is empty or absent in the surrounding card, extract the name from the img's filename (e.g., `.../accesshealthcare.png` → "Access Healthcare"). Expected effect: recovers the 9 empty-alt perotjain cards; also helps any WordPress-powered PE site.
- **Add URL-domain fallback** to `_extract_context_name` / the discovery filter: when neither link text nor any context path yields a name, derive the name from the target URL's domain (e.g., `endurancelift.com` → "Endurance Lift"). This also acts as a safety net for pages we haven't encountered yet.
- **Raise AI prompt truncation limits** in `discover_portfolio.py`: `page_text[:8000]` → `[:30000]`, `links_text[:3000]` → `[:10000]`, link count 100 → 300. Expected effect: AI path no longer truncates mid-portfolio on large firms.
- Validation logic (`ValidatePortfolioCompanies`) is **NOT** changed. It continues to filter false positives per-company with the existing yes/no AI call — still the right mechanism to exclude funds, tools, nav links, etc. from a larger candidate set.

## Capabilities

### New Capabilities

_(None — this change modifies recall/precision of an existing capability rather than introducing a new one.)_

### Modified Capabilities

- `async-portfolio-scan`: no requirement changes — the async dispatch, state lifecycle, and worker behavior are untouched. This change only widens the discovery funnel inside the existing pipeline. No spec delta needed.

## Impact

- **Modified**: `backend/src/data_strategies/portfolio_discovery_strategy.py` — remove the 30-cap, add URL-domain fallback when context name cannot be derived.
- **Modified**: `backend/src/data_strategies/web_scraper_strategy.py` — `_extract_context_name` gains img-filename fallback.
- **Modified**: `backend/src/pipeline/pipeline_steps/discover_portfolio.py` — raise AI prompt truncation limits.
- **Tests**:
  - `backend/tests/unit/data_strategies/test_portfolio_discovery.py` — assert we now return > 30 companies when the page has > 30, plus a test fixture mirroring the perotjain empty-alt pattern.
  - `backend/tests/unit/data_strategies/test_web_scraper_strategy.py` (or equivalent) — assert img-filename fallback + URL-domain fallback work.
- **No infrastructure changes**: reuses the SQS worker + existing AI pipeline. Validation fan-out is already parallel via `FutureManager`.
- **Cost awareness**: AI validation will run on more candidates for large firms. Pre-fix: ~22 validation calls on perotjain. Post-fix: potentially ~40-50 (70 total minus ~20-25 intersection with the AI extraction path). The async worker absorbs the extra latency; the token bill roughly doubles for firms of this scale. Acceptable tradeoff given the product impact.
- **Frontend**: no changes. The confirmation screen already renders a variable-length company list and the user can deselect entries.
