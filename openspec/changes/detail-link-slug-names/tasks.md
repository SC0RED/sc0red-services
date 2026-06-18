## 1. Slug-derived names for detail links

- [x] 1.1 Add a `_name_from_detail_slug(url)` helper in `portfolio_discovery_strategy.py`: take the URL path's last segment and title-case it via the existing `_title_case_tokens`, bounded by `MIN_NAME_LENGTH`/`MAX_NAME_LENGTH`; return "" if out of bounds.
- [x] 1.2 In the heuristic link loop, for `is_internal_portfolio` links, derive the name from the slug when the anchor-text name is unusable (generic CTA, empty, or out of the length bounds); keep the detail-page href as the candidate URL. Preserve a clean in-bounds anchor name unchanged.

## 2. Tests

- [x] 2.1 Detail link with long descriptive anchor text → slug-derived name + detail-page candidate URL (Francisco `/investments/8x8` shape).
- [x] 2.2 Slug with separators (`aeries-software` → "Aeries Software").
- [x] 2.3 Clean short anchor text is preserved (slug does not override).
- [x] 2.4 Non-detail same-domain link (e.g. `/investments` listing, `/about`) is not turned into a candidate.

## 3. Validation & verification

- [x] 3.1 `ruff check` + `ruff format` + naming validator + abbreviations clean on changed files
- [x] 3.2 `pyright src/` introduces no new error category
- [x] 3.3 `pytest tests/ -q` passes with coverage ≥ 95%
- [ ] 3.4 Run the `architecture-reviewer` agent; resolve CRITICAL before commit
- [x] 3.5 Reproduce locally: `franciscopartners.com/investments` now yields the full list of slug-named detail candidates (was ~1)
- [ ] 3.6 Run the E2E suite per CLAUDE.md before opening the PR
