## Why

`customer-guided-portfolio-discovery` made discovery transparent and gave customers recovery paths (verdict + message, upload, "Search deeper"). Dev verification surfaced a *trust* problem in the results themselves:

- **Web-search ("Search deeper") results are unreliable.** The same company appears twice under different TLDs (e.g. `xyz.com` and `xyz.in`), and URLs are model-guessed, not verified. The cross-source dedup keys on host+path only (`normalize_url_key`), so a company we already have *reliably from the firm's site* reappears as a web-search row.
- **The customer can't tell reliable from best-effort.** Every candidate is just `{name, url, description}` — site-scraped (authoritative) and web-searched (approximate) companies are indistinguishable in the list.
- **The "why it's incomplete" message is generic** and doesn't convey that we used the firm's own page where we could, nor what limit stopped us.
- **The only correction paths are upload and a broader (still unreliable) web search.** There's no way for a customer to say "you read the wrong page — the list is *here*."

## What Changes

- **Per-candidate provenance + confidence.** Each discovered company carries its `source` (site / web_search / upload / provided_url) and the site-derived group surfaces the exact firm page we read (e.g. `insightpartners.com/portfolio`). The UI marks reliable rows (✓ from the firm's site) distinctly from best-effort rows (~ found via search — verify), reusing the existing `ProvenanceMarker`.
- **Confidence-aware dedup — reliable source wins.** When merging web-search candidates into the trusted set (site/upload/provided-URL), suppress by **normalized name OR url-key**; a trusted entry always wins. This stops site companies from repeating in web search, collapses `xyz.com`/`xyz.in` TLD duplicates, and never drops a real holding.
- **Honest, specific incompleteness messaging.** Lead with the reliable part ("read N from the firm's site"), then explain the gap in plain terms — the site renders its portfolio client-side (in the browser, after load), so we can't read the full list from static HTML — without over-claiming a "cross-origin" block (our scraper is server-side).
- **Provide-a-reliable-URL correction path.** The customer can paste the URL of a page that actually lists the portfolio; we fetch it **server-side** and run the same trusted extraction — reliable, unlike a broader web search. Sits beside Upload as a second correction path.
- **Web-search rows are opt-in.** Reliable rows are pre-selected; web-search rows are shown unchecked under a "review before including" subhead so customers consciously opt into the fuzzy ones.

## Capabilities

### New Capabilities
- `portfolio-discovery-provenance`: every candidate carries source + confidence; the UI marks reliable vs best-effort and shows the exact site source; confidence-aware name+URL dedup makes the trusted source win; reliability-honest messaging.
- `portfolio-source-url`: customer-supplied "reliable source" URL fetched server-side as a trusted discovery source (a sibling of CSV/PDF upload).

## Impact

- **Backend:** thread `source`/provenance through the extraction output → `DiscoverPortfolio`/`DeepenPortfolio` merge → persisted verdict/candidates → scan read API + MCP; replace URL-only dedup with confidence-aware name+URL dedup (web-search vs trusted); a `scan_core` entry + scraper reuse for a provided source URL; enrich the verdict with a reliability reason.
- **Frontend:** provenance badges + the exact site source line; segregate + don't-pre-select web-search rows; a "Paste a page URL" affordance beside Upload; render the reliability reason.
- **Out of scope:** the headless-render (Playwright) rung (still deferred to its own change); reverse-engineering a firm's private portfolio API endpoint (noted as a power-user lever in design, not built); fuzzy name-matching beyond conservative suffix-stripping.

## Relationship to prior work

Builds directly on `customer-guided-portfolio-discovery` (verdict, escalation, upload — feature-complete on `development`). This change is the *trust/reliability* layer on top: who said so, how sure are we, and a reliable alternative to web-search guessing.
