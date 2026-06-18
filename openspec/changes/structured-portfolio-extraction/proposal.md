## Why

Portfolio discovery returns ~2 wrong companies for Thoma Bravo (`https://www.thomabravo.com/`) while the firm actually lists 151. Diagnosed locally: the `/portfolio` page embeds all 151 companies as **clean structured JSON** inside a 249 KB `<script>` hydration island — `{"name":"Calabrio","slug":"calabrio", …20 metadata fields…}`. The current pipeline captures that script but (1) **truncates** it at the 200 KB AI-prompt budget (keeps only 122/151) and (2) feeds the raw, deeply-nested escaped JSON to the **AI extractor**, where the company signal (`name`/`slug`) is buried under per-record logo/timestamp/dimension noise — so the LLM returns almost nothing and discovery falls through to a couple of weak heuristic links. The data is excellent; we just parse it the hard way. A one-line regex extracts all 151 records cleanly and deterministically.

## What Changes

- Add a **deterministic embedded-company extractor**: scan the data-bearing inline `<script>`(s) for repeated adjacent `"name":"…","slug":"…"` records (handling both plain and escaped/`\"`-stringified JSON) and return `(name, slug)` pairs. Run it on the **full** script content (the 200 KB cap exists only to bound the AI prompt; a parser does not need it), so all records are recovered, not just those before the cut.
- Surface these as a new `embedded_companies` field from `scrape_url`, threaded through `PortfolioDiscoveryStrategy` metadata.
- In `PortfolioDiscoveryStrategy`, turn each `(name, slug)` into a candidate whose URL is the firm's **own detail page** for that company (`{listing_page}/{slug}`, e.g. `thomabravo.com/portfolio/calabrio`). The existing per-company scan's URL-resolution step then resolves the company's real website from that page (verified: the detail page links out to `calabrio.com`).
- These structured candidates flow into the existing `DiscoverPortfolio` merge → `needs_validation` → AI validation → per-company scan, exactly like heuristic candidates. AI extraction stays unchanged as the fallback for sites without structured embedded JSON.
- No change to the curl_cffi transport, `_extract_data_scripts` density ranking, or the web-search fallback.

## Capabilities

### New Capabilities
- `embedded-portfolio-extraction`: Portfolio discovery deterministically parses structured company records (name + slug) embedded as JSON in a site's hydration scripts, and forms scannable candidate URLs from the firm's per-company detail pages — recovering the full list on SSR/headless-CMS sites where AI extraction over the raw script is unreliable.

### Modified Capabilities
<!-- None: this adds a new deterministic extraction path; existing discovery-merging / portfolio-discovery-recall requirements are unchanged. -->

## Impact

- **Code:** `src/data_strategies/web_scraper_strategy.py` (new `_extract_embedded_companies`; `scrape_url` returns `embedded_companies`), `src/data_strategies/portfolio_discovery_strategy.py` (consume `embedded_companies`, build detail-page candidate URLs, merge with the link heuristic). `DiscoverPortfolio` is unchanged — the new candidates ride the existing heuristic→merge path.
- **Behavior:** embedded-JSON portfolio sites (Thoma Bravo and similar Next.js/headless-CMS firms) yield the full company list reliably and deterministically, instead of depending on AI extraction over noisy truncated JSON.
- **Out of scope:** changing the AI extraction prompt/path (kept as the fallback); a fully generic JSON-schema crawler (the `name`+`slug` adjacency is a deliberate, common-shape heuristic, documented as such); the curl_cffi transport and web-search fallback.
