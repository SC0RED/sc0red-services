## Why

Portfolio discovery collapses an entire firm's portfolio down to one company when the candidates are the firm's own per-company **detail pages** (e.g. `thomabravo.com/portfolio/{slug}`). The merge step (`DiscoverPortfolio._merge_results`) deduplicates candidates by **domain only** — `_normalize_domain` compares netloc and explicitly ignores the path. Every detail-page URL shares the firm's domain, so 151 distinct Thoma Bravo companies collapse to 1 in the merge (the user sees ~2 after the AI path adds one). This is the real reason Thoma Bravo shows ~2 companies even though `structured-portfolio-extraction` correctly discovers all 151 at the strategy level — and it bites any site whose candidates are same-domain internal detail pages.

Confirmed locally on `development`: strategy returns 151 → `_merge_results` → `auto_included=0, needs_validation=1`.

## What Changes

- Make the discovery merge dedup **path-aware**: key candidates on normalized `netloc + path` (strip `www.`, lowercase, drop trailing slash, ignore query/fragment) instead of bare domain. Distinct same-domain detail pages (`/portfolio/a`, `/portfolio/b`) stay distinct; `www.`/trailing-slash variants of the *same* URL still match.
- Apply the same path-aware key in `_merge_fallback` (web-search fallback dedup) for consistency.
- External company URLs (root or root-with-slash) are unaffected — they normalize to the same key as before, so the heuristic ∩ AI intersection (auto-include) still works for company-site candidates.

## Capabilities

### Modified Capabilities
- `discovery-merging`: the merge/dedup key changes from netloc-only to netloc+path, so same-domain detail-page candidates are no longer collapsed into one company.

## Impact

- **Code:** `src/data_strategies` is untouched. Only `src/pipeline/pipeline_steps/discover_portfolio.py` — replace the netloc-only `_normalize_domain` used in `_merge_results` and `_merge_fallback` with a path-aware key helper. `DiscoverPortfolio`'s flow, `validate_portfolio` (no domain dedup), and the strategy (already dedups by full URL) are unchanged.
- **Behavior:** sites whose discovery yields internal detail-page URLs (Thoma Bravo and similar) return their full company list through the full pipeline, not just the strategy. External-company discovery is unchanged.
- **Known cost (not a regression):** when all candidates land in `needs_validation` (no AI intersection), each is AI-validated — more validation calls for large portfolios. Acceptable for the async scan; optimization is out of scope.
- **Out of scope:** the structured extractor / transport / web-search fallback (already shipped); name-level dedup of the same company appearing as both an internal detail page and an external site.
