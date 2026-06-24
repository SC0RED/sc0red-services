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

---

## Correction — dev verification findings (2026-06-22)

Verifying Phases 1+2 on dev against real firms (Insight Partners, General Atlantic, Summit, Alpine, Riverside, Audax) surfaced a design flaw in the verdict, plus a gap in the deepen flow. Captured here as decisions 6–8; supersedes the relevant parts of decisions 1, 2, and 4 and the first Open Question.

**Real scraper output (heuristic path, measured against the live sites):** Audax 4, Alpine 3, General Atlantic 19, Summit 104, Insight 0 (147 KB JS island), Riverside 0 (1 KB shell). None failed to fetch. So most of these firms return a **small, non-zero** `site_total`.

**6. The verdict must not infer completeness from a non-zero site count.**
The shipped `build_verdict` rule `site_total > 0 → full_site_list` is wrong. A non-zero site scrape is frequently a *partial* result (CSR shells, paginated JSON, logo grids that surface a handful). Treating "we found ≥1" as "we found everything" causes two coupled failures:
- the customer-facing message falsely claims "we read the firm's portfolio directly — N companies"; and
- `full_site_list` sets `available_actions = ["upload_list"]`, **hiding Search deeper** — so the customer can't escalate a thin result.
Ironically the #419–#425 scraper improvements *caused* this: firms that used to return 0 (→ web-search fallback → `web_search_subset` → Search deeper offered) now return a small N (→ `full_site_list` → escalation hidden). We made the scraper better and the verdict worse.
**Decision:** the verdict SHALL NOT hide escalation based on a non-zero count. `search_deeper` + `upload_list` are offered whenever the result may be incomplete. A non-zero-but-uncertain scrape is classified `partial_site_list` (message: "Found N from the firm's site — if that looks short, search deeper or upload your list"), not `full_site_list`. `full_site_list` is reserved for results we have positive reason to believe are complete; absent such a signal, default to `partial_site_list`.

**7. The thin-scrape auto-fallback gate is too strict.**
The web-search fallback runs only when `site_total <= _FALLBACK_THRESHOLD` (= 0), so a scrape of 4-of-200 (Audax) never auto-augments. **Decision:** raise the low-water mark so clearly-thin scrapes (e.g. `site_total` below a small N) auto-run the fallback, *and* rely on the customer-triggered Search deeper (decision 6) for the rest — keeping expensive work customer-gated in the common case while rescuing obviously-broken scrapes. (Exact N to be tuned from real data; start conservative.)

**8. Deepen must converge and report exhaustion so we can honestly redirect to upload.**
Today `run_deep_web_search_discovery` runs a *fixed* 3 angled passes, does not surface how many were *new*, and `build_verdict` always re-emits `web_search_subset` ("this firm likely has more") — so the system can never honestly say "we've dug as deep as web search allows." **Decision:**
- thread `added_this_round` (count of newly-found companies) out of `DeepenPortfolio` into the verdict;
- deepen converges — either loop angled passes within one click until a round adds nothing new (safety-capped), or detect a zero-delta round across clicks;
- on convergence, a new completeness tier `web_search_exhausted` whose message states web search found no more and directs the customer to **upload** for a guaranteed-complete list, and which stops presenting Search deeper as productive.
**Honesty caveat (applies throughout):** web search is *recall, not enumeration* — even an exhausted deeper search is not guaranteed complete. Upload remains the only path to a complete list; the messaging must say so plainly.

**Open question resolved:** the `completeness` taxonomy is extended with `partial_site_list` and `web_search_exhausted` (now six values: full_site_list, partial_site_list, site_blocked, web_search_subset, web_search_exhausted, genuinely_empty).
