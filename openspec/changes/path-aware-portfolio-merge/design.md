## Context

`structured-portfolio-extraction` (#421) made `PortfolioDiscoveryStrategy` return all 151 Thoma Bravo companies as detail-page candidates (`thomabravo.com/portfolio/{slug}`). But the user still sees ~2. Root cause, confirmed on `development`: `DiscoverPortfolio._merge_results` keys candidates by `_normalize_domain` (netloc only, path ignored — as the `discovery-merging` spec explicitly stated). All 151 candidates share `thomabravo.com`, so the by-domain dict collapses them to 1.

```
strategy companies: 151  →  distinct domains: 1  →  _merge_results: auto=0, needs_validation=1
```

The collapse bites any candidate set of same-domain internal detail pages. External-company candidates (one company ≈ one domain) are unaffected by the existing behavior.

## Goals / Non-Goals

**Goals:**
- Stop collapsing distinct same-domain detail-page candidates in the merge.
- Preserve the existing external-company behavior: `www.`/trailing-slash variants of the same URL still dedup; heuristic ∩ AI intersection (auto-include) still works for company-site URLs.
- Keep the change contained to the merge dedup key.

**Non-Goals:**
- Changing the structured extractor, transport, or web-search fallback (shipped).
- Name-level dedup of a company appearing as both an internal detail page and an external site.
- Optimizing the validation fan-out for large portfolios.

## Decisions

**1. Dedup key = normalized `netloc + path`, not bare netloc.**
Replace the netloc-only `_normalize_domain` (used in `_merge_results` and `_merge_fallback`) with a path-aware key: lowercase host with `www.` stripped, plus `path.rstrip("/")`, ignoring query/fragment. Distinct paths → distinct keys; same URL with `www`/slash differences → same key.

*Why this is safe for external companies:* their candidate URLs are typically roots (`company.com`, `company.com/`), which normalize to the same key (`company.com`), so intersection/auto-include is unchanged. The only behavioral change is for many-paths-on-one-domain, which is exactly the detail-page case we are fixing.

*Alternative — distinguish internal (firm-domain) vs external and key differently:* rejected as over-complex; the merge does not know the firm domain, and path-aware keying handles both cases acceptably. The rare downside (an external company appearing once as `company.com` and once as `company.com/about` would not dedup) is low-impact (a duplicate candidate that validation/scan tolerates) versus the catastrophic 151→1 collapse it fixes.

**2. Keep the intersection/auto-include semantics; only the key changes.**
`auto_included` still = candidates whose normalized key appears in both heuristic and AI; `needs_validation` still = the remainder. For Thoma Bravo, the internal detail pages won't match AI's external URLs, so all land in `needs_validation` and are AI-validated — correct, just more calls.

## Risks / Trade-offs

- **More validation calls for large portfolios** → 151 candidates each AI-validated when none intersect AI. Mitigation: bounded by the existing `FutureManager` worker cap; acceptable for the async scan. Not a correctness issue.
- **External company with two different paths no longer dedups** → at worst a duplicate candidate, filtered downstream by validation/scan. Far preferable to collapsing a whole portfolio.
- **Existing merge tests** use root-path external URLs (`a.com`, `stripe.com`) → path-aware key == domain for those, so they keep passing; add tests for the same-domain-distinct-path case.

## Migration Plan

1. Add a path-aware `_normalize_url_key` helper; use it in `_merge_results` and `_merge_fallback` (replace `_normalize_domain` there).
2. Tests: 151-style same-domain distinct-path candidates survive the merge; `www`/slash variants still dedup; external intersection still auto-includes; fallback dedup still works.
3. Validate + architecture review + E2E; deploy via branch promotion (this change plus the three already on `development`). Rollback = revert the PR.

## Open Questions

- None. The change is a contained dedup-key fix with preserved external-company semantics.
