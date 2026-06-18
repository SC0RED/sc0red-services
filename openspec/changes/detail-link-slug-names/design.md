## Context

Francisco Partners is a fifth portfolio site shape (after embedded-JSON, TLS-blocked, logo-grid, and plain anchor-link). Its `/investments` page links 176 companies as `/investments/{slug}` detail pages, but the anchor text is a long description, not the name. The heuristic uses anchor text → all exceed the 60-char cap → dropped; the AI surfaces ~1. The name is in the slug, and the detail page links out to the real company (`/investments/8x8` → `8x8.com`), so slug-named candidates are scannable via the existing URL-resolution step.

## Goals / Non-Goals

**Goals:**
- Recover anchor-link portfolios whose detail links carry the name in the slug, not the text.
- Keep the candidate URL as the internal detail page (resolves downstream).
- Don't regress sites where the anchor text is the company name.

**Non-Goals:**
- New scrape output or transport changes.
- Touching the merge (path-aware already keeps distinct detail paths) or validation.
- Headless rendering (deferred).

## Decisions

**1. Slug-derived name only when anchor text is unusable, only for internal detail links.**
The existing loop already falls back to a context/URL name for generic-CTA or empty anchors. Extend that: for `is_internal_portfolio` links, when the chosen name is out of the length bounds (the descriptive-text case) or empty/CTA, derive the name from the last path segment via the existing title-casing. A clean in-bounds anchor name is used as-is. This is the minimal, targeted change that fixes Francisco without affecting clean-anchor sites.

**2. Reuse the existing title-casing, no web_scraper growth.**
`web_scraper_strategy.py` is at the 400-line audit limit, so the slug→name helper lives in `portfolio_discovery_strategy.py` and reuses the existing token title-caser (`_title_case_tokens`) rather than duplicating it. The helper takes the URL path's last segment and title-cases it, bounded by the existing name limits.

**3. Candidate URL = the internal detail page.**
The slug names the company; the detail-page href is the scannable URL. The per-company scan's URL resolution finds the real company site from it (verified: `/investments/8x8` → `8x8.com`). Consistent with the Thoma Bravo detail-page approach.

## Risks / Trade-offs

- **Cryptic slugs** (e.g. numeric IDs) → title-cased to a poor name. Bounded: such candidates are still validated and individually scanned; a bad name is cosmetic and the URL resolution still works. Length bounds drop empty/degenerate slugs.
- **Over-broad application** → guarded by `is_internal_portfolio` (path must contain a portfolio segment + slug) AND by only overriding when the anchor text is unusable, so clean-anchor sites are untouched.
- **Slug ≠ company name occasionally** → the scan resolves the real site regardless; validation filters non-companies.

## Migration Plan

1. Add a slug→name helper in `portfolio_discovery_strategy.py` (reusing `_title_case_tokens`).
2. In the heuristic loop, apply it for internal detail links when the text-derived name is out of bounds / CTA / empty.
3. Tests: descriptive-text detail link → slug name + detail URL; slug with separators; clean anchor text preserved; non-detail same-domain link unaffected; live Francisco check.
4. Validate + architecture review + E2E; deploy via branch promotion with the others. Rollback = revert the PR.

## Open Questions

- None — the change is a contained heuristic name-derivation improvement.
