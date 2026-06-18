## Context

After #419–#422, three site shapes are handled: embedded-JSON (TB), TLS-blocked (Gainsight), anchor-link grids. Vista is a fourth shape: a **logo-image grid**. Confirmed on `development`:
- `/companies` (and `/about/companies/`) carry ~68 companies as `<img alt="Logo of software company {Name}">`, unlinked, no detail pages (404), no company URLs on the page.
- `scrape_url` reads 0 (alt text isn't body text, links, or a JSON island); AI-visible body text has zero portfolio names.
- Site path → 0 → web-search fallback fires, but its conservative prompt returns ~2.

So Vista needs both the **names** (on the page, in logo alt) and the **URLs** (not on the page → web search). The chosen approach: extract the names from the logo grid and seed a single grounded call to resolve URLs.

## Goals / Non-Goals

**Goals:**
- Read company names from logo-`alt` grids.
- Resolve their URLs by seeding one grounded web-search call with the on-site names.
- Broaden the unseeded fallback for opaque sites with no logo grid.
- Stay additive: no change to embedded-JSON / anchor-link / TLS paths; fallback still fires only when the site path yields nothing.

**Non-Goals:**
- Guessing `name → companyname.com` without web search (unreliable).
- One grounded call per company (cost/latency).
- Headless rendering (Playwright remains deferred).

## Decisions

**1. Logo-alt extraction, precision-first.**
`_extract_logo_companies(soup)` matches logo `alt` patterns — primarily `(?i)logo of (?:the )?(?:software |portfolio )?company (.+)` and secondarily `(?i)^(.+?) logo$` — strips trailing punctuation, applies the existing `MIN_NAME_LENGTH`/`MAX_NAME_LENGTH` bounds, excludes the firm's own name, dedups case-insensitively. Precision over recall: false positives cost a wasted URL lookup, and the seeded model / validation drop non-companies. Captured before script/clutter stripping (like the other extractors).

**2. Names are SEEDS, not companies.**
Logo names have no URL, so they must not be counted as discovered companies (that would both suppress the fallback and emit unscannable candidates). They are carried separately (`logo_company_names`) and only consumed by the fallback. This keeps `site_total` at 0 for Vista, so the fallback still fires.

**3. Seed the existing fallback; one grounded call.**
`_run_web_search_fallback(firm_url, seed_names)` renders a template with an optional known-companies block: with seeds → "here are the firm's portfolio companies: […]; return each company's official website URL, and add any other current holdings"; without seeds → "find as many current holdings as you can." Schema unchanged (`{companies:[{name,url}]}`). The model grounds each name to its official site — an easier task than open-ended portfolio recall, which is why seeding fixes the under-return.

**4. URLs are external company sites → distinct domains.**
Resolved candidates (`jamf.com`, `datto.com`, …) are distinct domains, so the path-aware merge (#422) keeps them distinct, and validation + per-company scan proceed normally.

## Risks / Trade-offs

- **Logo-alt false positives** (partner/press logos) → seeded into web search; the model finds no real URL or validation drops them. Bounded.
- **Seeded model still under-returns or returns wrong URLs** → candidates are validation-tier and individually scanned; wrong URLs fail gracefully. We pass authoritative names, so recall is driven by the site, not the model's memory.
- **`/companies` vs `/about/companies/`** → `/companies` already returns the grid (200) and is in `PORTFOLIO_PATHS`; no path change required, though `/about/companies/` could be added for robustness.
- **Generality** → the logo-alt patterns are common but not universal; purely additive, so non-matching sites are unaffected.

## Migration Plan

1. `_extract_logo_companies` + `scrape_url` `logo_company_names` (additive).
2. Thread `logo_company_names` through `PortfolioDiscoveryStrategy` metadata.
3. `_run_web_search_fallback(firm_url, seed_names)`; pass seeds from `execute`; seeded/unseeded prompt.
4. Tests (logo-alt extraction incl. firm-logo exclusion & cleanup; seeded vs unseeded prompt selection; fallback still gated on site_total==0; merge keeps distinct external URLs).
5. Validate + architecture review + E2E; deploy via branch promotion with the others. Rollback = revert the PR (additive).

## Open Questions

- Exact logo-alt pattern set — start with the two above; widen only if real sites show other forms (additive, low-risk).
