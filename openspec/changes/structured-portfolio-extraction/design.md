## Context

`resilient-portfolio-discovery` made the scraper capture data-bearing `<script>` JSON (`script_text`) and feed it to the AI extractor; `tls-impersonating-scraper` made the fetch pass Cloudflare. Both shipped. A new failure surfaced on Thoma Bravo: the `/portfolio` page embeds **151** companies as structured JSON in a 249 KB hydration island, but discovery returns ~2 junk candidates.

Diagnosed locally (current `development`):
- The island IS captured (densest script, selected by `_extract_data_scripts`).
- `_MAX_SCRIPT_TEXT_LENGTH = 200_000` truncates the 249 KB island → only 122/151 records survive into `script_text`.
- Each record is large and noisy (`logoSolidBlack` with timestamps/dimensions/blob URLs, `thumbnailURL`, `sectors`, `platforms`, …). Feeding 200 KB of escaped JSON to the AI extractor yields almost nothing usable, so discovery falls back to the heuristic links — the homepage's 6 "See X case study" anchors — and the merged result is a couple of weak candidates.
- A regex for adjacent `"name"`/`"slug"` extracts all 151 records cleanly. The records carry `name` + `slug` but no company website (the only `url` is the logo image). The firm detail page `thomabravo.com/portfolio/{slug}` links out to the real site (verified: `…/calabrio` → `calabrio.com`).

## Goals / Non-Goals

**Goals:**
- Recover the full embedded company list deterministically on structured-JSON portfolio sites.
- Produce scannable candidate URLs without an extra AI call per company.
- Reuse the existing merge → validation → per-company scan path; no change to `DiscoverPortfolio`.

**Non-Goals:**
- Replacing AI extraction (kept as the fallback for unstructured sites).
- A generic JSON-schema crawler — the `name`+`slug` adjacency is a deliberate common-shape heuristic.
- Changing the curl_cffi transport, density ranking, or web-search fallback.

## Decisions

**1. Deterministic `name`+`slug` parser, not AI, for structured records.**
Add `_extract_embedded_companies(soup)` in `web_scraper_strategy.py`: over the inline data scripts (full content, pre-truncation), match adjacent `"name":"…","slug":"…"` (plain and escaped `\"…\"`) → `[{name, slug}]`, deduped by slug. *Alternative — raise the AI budget and keep relying on the LLM:* rejected; it is slower, costs tokens, non-deterministic, and still drowns in per-record noise. Determinism + completeness win for structured data.

**2. Requiring adjacency filters noise.**
Only `name` immediately followed by `slug` qualifies, so logo assets (`{"alt":…,"name":…}`) and `searchableNormalized:{"name":…}` (no adjacent slug) are excluded. This is the discriminator that separates company records from the surrounding metadata.

**3. Parse the full script, not the 200 KB-capped `script_text`.**
The cap exists only to bound the AI prompt. The deterministic parser runs on the uncapped script content so all 151 (not 122) are recovered. `script_text` and the AI path keep the cap.

**4. Candidate URL = listing page + slug; resolve downstream.**
The record has no company website, so the candidate URL is the firm's own detail page (`{listing_page}/{slug}`), mirroring what the link heuristic already produces for featured companies. The existing per-company scan URL-resolution step resolves the real site from there. *Alternative — web-search each name to get the official site up front:* rejected for the default path (an extra grounded AI call × 151 = latency/cost); the detail-page+resolve path is consistent and free. (Web-search remains available as the zero-yield fallback.)

**5. Home the new path in `PortfolioDiscoveryStrategy`, feeding the existing merge.**
The strategy already loops `PORTFOLIO_PATHS`, so it knows each page URL and can build `{page_url}/{slug}`. The structured candidates join the heuristic-link candidates; `DiscoverPortfolio`'s merge (intersection→auto_included, remainder→needs_validation) is untouched.

## Risks / Trade-offs

- **Slug→URL is a heuristic** → a site whose detail pages are not nested under the listing path yields URLs that 404. Mitigation: such candidates fail validation / resolution gracefully (dropped, not fatal); the AI and web-search paths still run.
- **`name`+`slug` shape is not universal** → sites using a different record shape get nothing from this path. Mitigation: it is purely additive; the existing heuristic/AI/web-search paths are unchanged, so no regression — only upside on the common shape.
- **Over-matching** → a non-company object that happens to have adjacent `name`+`slug`. Mitigation: validation tier + AI validation + per-company scan filter false positives; candidates are never auto-included.
- **Duplicate signal** → the same company found by both the link heuristic and the structured parser. Mitigation: existing URL-domain dedup in the merge.

## Migration Plan

1. Implement `_extract_embedded_companies` + `scrape_url` `embedded_companies` field (additive; existing callers unaffected).
2. Consume it in `PortfolioDiscoveryStrategy`, build detail-page candidates, merge.
3. Tests: TB-shaped escaped-JSON fixture → all records; noise objects excluded; plain-JSON fixture; no-records site unchanged; candidate URL construction; dedup against heuristic links.
4. Validate + architecture review + E2E; deploy via the standard branch promotion. Rollback = revert the PR (additive change, no data migration).

## Open Questions

- Detail-path derivation: default to `{listing_page}/{slug}`. If real data shows firms nesting detail pages elsewhere, infer the prefix from an observed heuristic link instead — deferred until observed.
