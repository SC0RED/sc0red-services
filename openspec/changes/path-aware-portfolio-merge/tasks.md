## 1. Path-aware merge dedup

- [x] 1.1 Add `_normalize_url_key(url)` to `discover_portfolio.py`: lowercase host with `www.` stripped + `path.rstrip("/")`, ignoring query/fragment (root path → just host).
- [x] 1.2 Use `_normalize_url_key` in `_merge_results` (both `heuristic_by_*` and `ai_by_*` keying) so distinct same-domain detail pages stay distinct.
- [x] 1.3 Use `_normalize_url_key` in `_merge_fallback` (the `seen` set and per-candidate key).
- [x] 1.4 Remove `_normalize_domain` if it has no remaining callers, or keep only if still used elsewhere.

## 2. Tests

- [x] 2.1 `_merge_results`: many same-domain distinct-path candidates (e.g. `firm.com/portfolio/a..z`) all survive (no collapse); count preserved.
- [x] 2.2 `_merge_results`: external company found by both paths as `company.com` / `www.company.com` → auto-included (still intersects).
- [x] 2.3 `_merge_results`: `https://x.com` vs `https://x.com/` (root, slash) → treated as one.
- [x] 2.4 `_merge_fallback`: dedup against site results still works for external URLs; distinct-path site candidates not over-collapsed.
- [x] 2.5 Update any existing merge tests that asserted domain-only behavior, if affected.

## 3. Validation & verification

- [x] 3.1 `ruff check` + `ruff format` + naming validator + abbreviations clean on changed files
- [x] 3.2 `pyright src/` introduces no new error category
- [x] 3.3 `pytest tests/ -q` passes with coverage ≥ 95%
- [x] 3.4 Run the `architecture-reviewer` agent; resolve CRITICAL before commit
- [x] 3.5 Reproduce end-to-end locally: strategy(151) → `_merge_results` now yields ~151 (auto_included + needs_validation), not 1
- [x] 3.6 Run the E2E suite per CLAUDE.md before opening the PR
