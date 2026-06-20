## Context

After seven scraper/discovery fixes (#419–#425), discovery handles embedded-JSON, logo-grid, anchor-slug, TLS-blocked, and intermittent-fetch sites. Insight Partners exposes the remaining floor: a pure client-side-rendered portfolio (300+ companies fetched via a client-side API; nothing in the static HTML). The web-search fallback fires correctly but a single grounded call returns ~3 of 300. No parser recovers data that isn't fetched.

The product answer (customer's direction): stop presenting a silent partial result. Run cheap methods first, **explain the outcome**, and let the customer **escalate or correct** it — with expensive methods gated behind their explicit choice, and a CSV/PDF upload as a guaranteed correction.

## The escalation ladder

```text
 TIER       METHOD                            COST      TRIGGER
 0 site     embedded JSON / logo / anchors    ~free     auto
 1 quick    single web-search fallback        1 call    auto (site thin/blocked)
 ──────────── verdict + message + choices on the confirmation screen ────────────
 2 deeper   broader / multi-pass web search   few calls customer: "Search deeper"
 3 render   headless browser (Playwright)     slow $$   customer: "Render the site"  [deferred impl]
 U upload   customer CSV/PDF of companies     ~free     customer: "Upload a list"
```

Tiers 0–1 run automatically (current behavior). The `awaiting_confirmation` pause is the escalation hub — it already stops for customer review.

## Goals / Non-Goals

**Goals:**
- Replace the bare count with a verdict the customer understands (what we did, how complete, what to do next).
- Let the customer escalate (deeper search; render as a defined opt-in rung) and correct (CSV/PDF upload) — expensive tiers only on request.
- Reuse existing infra (document extraction, document-upload UI, the validation/scan path).

**Non-Goals:**
- Building the Playwright engine in this change (defined as a rung, deferred).
- Firm-specific portfolio-API scraping.
- Auto-running expensive tiers without customer consent.

## Decisions

**1. Discovery returns a structured verdict.**
`DiscoverPortfolio` emits `discovery_verdict`: `method` (site / web_search / upload), `count`, `completeness` (one of `full_site_list`, `site_blocked`, `web_search_subset`, `genuinely_empty`), and `available_actions` (subset of `search_deeper`, `render_site`, `upload_list`). The UI maps `completeness` → a plain-language message and renders `available_actions` as buttons. Derived from signals we already have (`site_fetch_failed` #425, which path produced candidates). A client-side-rendered firm (empty site scrape, web-search subset) maps to `web_search_subset` — we don't separately distinguish "CSR" from "genuinely few", as the message and next actions are the same.

**2. Escalation re-enters discovery at a chosen tier (resumable, not one-shot).**
`scan_core` gains an escalate entry (e.g. `deepen_scan(scan_id, tier)`) that re-runs discovery for an existing scan at the requested tier and merges new candidates into the existing set (deduped via the path-aware key from #422), returning to `awaiting_confirmation` with an updated verdict. Keeps the customer in control; no expensive work without a click. Same dispatch for UI and MCP (per the scan_core parity rule).

**3. CSV/PDF upload → candidates, reusing document extraction.**
A customer-supplied CSV (name[,url] columns) or PDF (best-effort text → names) is parsed into `{name, url?}` candidates and enters the existing validation → per-company scan path (URL resolved when absent). Reuses `src/documents/extract_text.py` and the document-upload UI. CSV is first-class (structured); PDF is best-effort. This is the always-correct override for any site.

**4. Deeper web search = broader prompt + optional multiple passes.**
Tier 2 widens the grounded search (higher target count, possibly sector/round-segmented passes) — bounded, still not able to enumerate 300, but lifts Insight-class firms from ~3 to a meaningful set. Honest cap, surfaced in the verdict.

**5. Playwright is a defined rung, deferred.**
`render_site` appears as an available action with clear cost framing, but the engine (chromium-in-Lambda) is its own change. Until built, choosing it surfaces "not yet available — try deeper search or upload your list." This honors "ask the customer before Playwright" without taking the infra hit now.

## Risks / Trade-offs

- **Scope** → phased: P1 verdict+messaging+upload (no heavy infra, immediate transparency+correction), P2 deeper search, P3 Playwright (separate). Each phase ships independently.
- **Resumable discovery adds scan states** → keep it additive to `async-portfolio-scan`; re-entering discovery returns to the same `awaiting_confirmation` contract.
- **PDF parsing is messy** → CSV-first, PDF best-effort; the verdict tells the customer what we extracted so they can correct.
- **Customer confusion from too many choices** → show actions contextually (only when the result looks incomplete), with one clear primary ("Proceed with these N").

## Migration Plan

1. **P1:** `discovery_verdict` from `DiscoverPortfolio`; UI message + (initially inert) action affordances; CSV/PDF upload → candidates → existing scan path; tests + E2E.
2. **P2:** `deepen_scan` escalate entry + deeper web-search tier wired to "Search deeper".
3. **P3 (separate change):** Playwright render rung.
Deploy via branch promotion; each phase is its own PR. Rollback = revert the phase PR.

## Open Questions

- Verdict `completeness` taxonomy — start with the five above; refine from real scans.
- CSV schema — accept `name` only and resolve URLs, or `name,url`? (Lean: accept both; `name` required, `url` optional.)
- Escalation surface — confirmation screen (recommended) vs a dedicated discovery panel.
