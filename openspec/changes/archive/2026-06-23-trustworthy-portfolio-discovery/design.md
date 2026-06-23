## Context

Discovery now produces a *mixed* candidate list — some companies read from the firm's own site (authoritative, exact URL), some recalled via web search (approximate, model-guessed URLs). The shipped model can't express that mix: `discovery_verdict.method` is a single value for the whole result, and each candidate is a bare `{name, url, description}`. Two concrete failures observed on dev:

- The same company appears under two TLDs (`xyz.com`, `xyz.in`) because `normalize_url_key` (host+path) treats them as distinct, and there is no name-level dedup.
- A company already found reliably on the firm's site reappears as a web-search row, for the same reason.

Grounding note: the frontend `ProvenanceMarker` component was written anticipating this — its docstring reserves `'from-scrape'` / `'from-upload'` kinds "when the backend gains a richer provenance schema." This change is that schema.

## Goals / Non-Goals

**Goals:** make reliability legible (per-candidate provenance + confidence); make the trusted source win in dedup; explain the gap honestly; add a reliable alternative to web-search guessing (provide-a-URL).

**Non-Goals:** Playwright render rung (separate, deferred); auto-discovering a firm's private JSON API (power-user lever, noted not built); ML/fuzzy name matching (conservative suffix-stripping only).

## Decisions

**1. Provenance + confidence live on each candidate, not the whole result.**
Each candidate gains `source ∈ {site, web_search, upload, provided_url}`. Confidence is derived, not stored: `web_search → low`, everything else `→ high`. The verdict summarizes the mix (counts per source) and carries the exact site page read (`site_source_url`, e.g. `insightpartners.com/portfolio`) as the group-level trust anchor. Per-company provenance for site results is "appeared on the firm's page we read" — the company's own URL is still its `url`; the *provenance* is the firm page, surfaced once for the group.

**2. Confidence-aware dedup — the trusted source always wins.**
Precedence: `site ≈ provided_url ≈ upload (high) > web_search (low)`. When merging web-search candidates into the trusted set, drop a candidate whose **normalized name** OR **url-key** already exists in the trusted set; only genuinely-new names survive. Normalized name = lowercased, common suffixes stripped (`Inc/LLC/Ltd/Corp/Co/GmbH/SA`), punctuation/whitespace collapsed — conservative to avoid merging distinct firms. We only ever drop a *web-search* twin, never a trusted holding, so a real company is never lost. This replaces the URL-only `merge_fallback`/deepen dedup and fixes both the cross-source repeat and the TLD-duplicate.

**3. Honest incompleteness messaging — reliable-first, no false "cross-origin" claim.**
Lead with what's trustworthy ("We read N companies directly from `firm.com/portfolio`"), then the gap. Our scraper is **server-side** (curl_cffi), so the blocker is NOT a browser cross-origin restriction — it's **client-side rendering**: the site's own JS fetches the portfolio from an API after the page loads, and we read static HTML. Customer-facing phrasing: "this firm's site builds its portfolio list in the browser after the page loads, so we couldn't read the complete list directly." Derive the reason from existing signals (large `script_text` + tiny `page_text` ⇒ dynamic; `site_fetch_failed` ⇒ blocked).

**4. Provide-a-reliable-URL is "upload, but a link."**
The customer pastes the URL of a page that lists the portfolio (their `/investments` page we missed, or a source they trust). We fetch it **server-side** with the existing scraper/extraction → `source=provided_url`, high confidence, exact. No browser cross-origin issue (server-side fetch). Caveats surfaced to the customer: if the provided page is itself client-side-rendered we hit the same wall; third-party sources may block us or violate ToS. Reuses the scraper + a `scan_core` escalate entry mirroring deepen/upload.

**5. Web-search rows are opt-in.** Reliable rows (site/upload/provided_url) are pre-selected; web-search rows render unchecked under a "Found via search — review before including" subhead, with unverified-URL flagging. The customer consciously includes the fuzzy ones.

## Risks / Trade-offs

- **Name-dedup over-merge**: two genuinely-different same-named firms in one portfolio. Mitigated: web-search-only, conservative suffix-stripping, trusted entry always retained (never lose a real holding).
- **Provenance plumbing reach**: source must thread extraction schema → merge → persistence → scan API → MCP → frontend. Incremental, but touches several layers; the `ProvenanceMarker` hook and existing verdict pipeline reduce risk.
- **Provide-a-URL on a CSR page**: same wall as the original scrape; set expectations in the UI rather than promising success.
- **"site_source_url" granularity**: AI-extraction knows the firm page it read, not per-company provenance — group-level anchor is sufficient and is what conveys trust.

## Migration Plan

Phased, each its own PR; no data migration (additive verdict/candidate fields; legacy verdicts without `source` render as today):
1. **Confidence-aware dedup** (rule #2) — smallest, highest-reliability; could even land in the current epic before it archives.
2. **Provenance + confidence** (rule #1) backend → frontend badges + site-source line + opt-in web-search rows (rule #5).
3. **Honest messaging** (rule #3) — verdict reason + copy.
4. **Provide-a-reliable-URL** (rule #4) — `scan_core` entry + UI affordance.

## Open Questions

- Where does the site-source URL come from for the AI-extraction path — the scraped page URL in metadata, or the per-company detail link when the heuristic found one? (Lean: the firm page actually fetched, captured in scrape metadata.)
- Should `provided_url` results merge *into* the existing scan (like deepen) or *replace* the web-search rows? (Lean: merge, trusted-wins.)
- Suffix-strip list for name normalization — start minimal, extend from real data.
