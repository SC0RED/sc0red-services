## Why

Francisco Partners (`franciscopartners.com`) shows only ~1 portfolio company though it lists ~176. Diagnosed on `development`: its `/investments` page links every company as an internal detail page (`/investments/{slug}`, e.g. `/investments/8x8`, `/investments/aeries-software`), but the **anchor text is a description**, not the name ("K-12 student information system…", median 110 chars). The heuristic link filter uses the anchor text as the company name, so all 176 candidates exceed the 60-char name cap and are dropped; the AI path then surfaces ~1 from the page text. The company name is sitting in the slug, and the detail page resolves to the real company (`/investments/8x8` → `8x8.com`).

## What Changes

- In the heuristic link filter, for **internal portfolio detail links** (`/portfolio/{slug}`, `/companies/{slug}`, `/investments/{slug}`), derive the company name from the URL **slug** (last path segment, title-cased) when the anchor text is unusable as a name — i.e. too long/descriptive, a generic CTA, or empty. The href stays the candidate URL (an internal detail page that the per-company scan's URL-resolution step turns into the real company site, exactly like the embedded-JSON detail-page path).
- Links whose anchor text already IS a clean, in-bounds company name are unchanged.

## Capabilities

### New Capabilities
- `detail-link-slug-names`: derive portfolio company names from internal detail-page URL slugs when the anchor text is descriptive rather than a name, so anchor-link portfolios (e.g. Francisco Partners' `/investments/{slug}`) are recovered in full.

### Modified Capabilities
<!-- None at the spec level: this strengthens the heuristic's name derivation within the existing discovery flow; merge/validation are unchanged. -->

## Impact

- **Code:** `src/data_strategies/portfolio_discovery_strategy.py` — the heuristic link loop's name-derivation; a small slug→name helper (reusing the existing title-casing). No change to `scrape_url`, the merge, or validation.
- **Behavior:** anchor-link portfolios whose link text is descriptive (Francisco Partners and similar) recover all companies; the slug-derived candidates ride the existing path-aware merge → validation → per-company scan (which resolves the real company site from the detail page). Sites with clean anchor-text names are unaffected.
- **Out of scope:** the curl_cffi transport, embedded-JSON / logo-grid / web-search paths (already shipped); headless rendering (Playwright remains the deferred escalation).
