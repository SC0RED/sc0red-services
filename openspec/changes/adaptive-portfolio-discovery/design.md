# Design — Adaptive portfolio discovery (delivery-mechanism classifier + routing)

Captured from an explore session. **Not a commitment** — it records the model, the
signature catalog, and the open spikes so the eventual work starts from facts.

## The core reframe

Rendering a page (headless) is **near the bottom** of the reliability ladder: it
hands back a messy DOM you still parse probabilistically. The *most* reliable
representation is the **structured source the page itself used** (a JSON endpoint
or an embedded hydration payload). So the goal for every firm is "climb to the
highest-reliability source it will give up," and the job of discovery is to figure
out *which rung a given firm sits on* and fetch accordingly — instead of blindly
trying everything.

## Why classify-then-fetch is a trap (and what to do instead)

You cannot classify without fetching (to know it's "static HTML" vs "CSR shell"
you must already have the HTML), and the act of fetching+parsing often *is* the
extraction. A pure up-front classifier-gate also can't see the deeper tiers ("is
there a `/api/portfolio`?", "is the list behind a tab?") — those are only knowable
by attempting them.

So the shape is **triage + self-classifying escalation ladder**:

```text
GET html (once)
   │
   ▼ TRIAGE on the HTML we already have (signatures below)
   │   → delivery_mechanism + confidence  (prunes/reorders the ladder; never hard-gates)
   ▼ enter the ladder AT the routed rung; each rung self-classifies by succeeding
 Tier-1 parse → Tier-2 endpoint probe → Tier-3 render → Tier-4 drive → Tier-5 vision/external/human
                (rung succeeded? enough companies? → stop; else escalate)
```

The triage **optimizes** the ladder (skip rungs that can't work, jump to the one
that will); the ladder is the safety net (a wrong guess just wastes a cheap rung).

## The killer value: the classifier explains a *thin* result

Low yield is ambiguous today. The mechanism disambiguates it, which decides
whether escalating (esp. expensive headless render) will even help:

| classifier says | found | meaning | action |
|---|---|---|---|
| static server-rendered HTML | 2 | genuinely small firm | **stop** — don't render |
| CSR empty shell, no SSR list | 0 | we missed everything | **escalate** (probe API / render) |
| behind a sector-filter tab | 12 | more tabs unread | **drive** the tabs |
| logos baked into one image | 0 | list is pixels | **vision / upload** |

This is the feature's spine: render (and other costly rungs) fire **only when the
mechanism proves hidden data exists**.

## Full taxonomy of how an investor site displays its portfolio

```text
A. ALREADY IN THE FIRST HTTP RESPONSE  (one GET; no JS needed to GET data)
   A1  Server-rendered HTML — visible <a>/<li>/cards
   A2  Embedded hydration JSON in <script>  (the data is shipped, JS only renders it
        — incl. the "scroll reveals it, no XHR" / virtualized-list case)
   A3  All rows in HTML but CSS/JS-paginated or filtered client-side
B. FETCHED BY JS AFTER LOAD
   B1  Single XHR/fetch → JSON API on load
   B2  Paginated XHR — infinite scroll / "load more" / numbered pages (network fires)
   B3  GraphQL endpoint (POST query) — harder to replay
   B4  Third-party backend — Algolia · Contentful/Sanity/Prismic · Airtable · Google Sheet
   B5  Framework data route — Next /_next/data/<buildId>/…json · RSC flight fetch
C. INTERACTION-GATED
   C1  Tab/accordion (Current vs Realized, sector tabs)
   C2  Search-only — must type to see anything
   C3  "Load more" button (click-driven B2)
   C4  Region selector / cookie/consent / modal gate
   C5  Carousel/slider lazy-mounting slides
D. NOT REALLY HTML
   D1  Downloadable PDF / fact-sheet
   D2  Embedded iframe (subdomain or 3rd-party widget)
   D3  Logos baked into one image/infographic    → OCR/vision
   D4  <canvas>/WebGL paint (not in DOM)          → screenshot + vision
   D5  Video/animation reel                        → vision
E. ENUMERABLE OUT-OF-BAND
   E1  sitemap.xml → /portfolio/<slug> detail URLs
   E2  RSS/Atom feed
   E3  One detail page per company; listing is the index
F. CROSS-CUTTING COMPLICATIONS (layer on ANY of A–E)
   F1  Bot wall — Cloudflare/Akamai JS challenge · CAPTCHA
   F2  Geofencing      F3  Auth wall (LP portal)      F4  Lazy-loaded images
```

### Collapse to 5 fetchability tiers (this is the routing target)

```text
TIER 1  plain GET + deterministic parse        A1 A2 A3 E1 E2        no browser, no AI   ★★★★★
TIER 2  plain GET to a *discovered* endpoint    B1 B2 B4 B5 (B3 hard) find URL → fetch    ★★★★★
TIER 3  needs JS exec, no interaction           CSR paint-on-load     headless render      ★★★
TIER 4  needs scripted interaction              C1–C5, load-more      headless + drive     ★★
TIER 5  needs vision or a human                 D1 D3 D4 D5, F1        OCR/vision / upload  ★/—
```

Note: most of B (the XHR family) pulls **up to Tier 1–2** if we find the endpoint —
which is why "discover the API" beats "render the DOM," and why a CSR firm is often
*not* actually a Tier-3 problem.

## Signature catalog (the heuristic triage — heuristics first, LLM for residue)

Read from the first fetched HTML (+ a couple of cheap follow-up GETs). Deterministic,
explainable, zero token cost for the common cases.

**Tier 1 — data already present**
- A1 server-rendered list: ≥N `<a href>` matching `/(portfolio|companies|investments|our-companies|holdings)/` with company-like text, or repeated card structures.
- A2 hydration payloads:
  - Next.js (pages): `<script id="__NEXT_DATA__" type="application/json">` → parse, hunt arrays of objects with name/slug/url keys.
  - Next.js (app router/RSC): `<script>self.__next_f.push(` flight payload.
  - Nuxt: `window.__NUXT__=` or `<script id="__NUXT_DATA__">`.
  - Gatsby: `/page-data/.../page-data.json` references.
  - Generic state: `window.__INITIAL_STATE__=`, `window.__DATA__=`, `__APOLLO_STATE__`.
  - JSON-LD: `<script type="application/ld+json">` with `@type` Organization / ItemList.
  - Bare `<script type="application/json">` blobs.
- A3 / virtualized (#3): react-window/react-virtualized markers + a large embedded data array ⇒ data is all present ⇒ treat as Tier 1.

**Tier 2 — discover & hit an endpoint**
- WordPress: `<link rel="https://api.w.org/">`, `/wp-json/` refs, `wp-content/` assets, `meta generator=WordPress` → probe `/wp-json/wp/v2/{posts,pages,<cpt>}` and likely CPTs (`portfolio`, `companies`, `investments`).
- Empty shell + bundle: empty `<div id="__next">`/`#root`/`#app` + `<script src=…/(portfolio|main|app).<hash>.js>` ⇒ CSR; data endpoint lives in the bundle / network.
- Algolia: `algoliasearch`, `*-dsn.algolia.net`, `X-Algolia-API-Key`, app-id+search-key in JS (usually public).
- Headless CMS: `cdn.contentful.com`, `*.api.sanity.io`/`apicdn.sanity.io`, `*.cdn.prismic.io`, `api.airtable.com`, `spreadsheets.google.com`.
- Next data route: `/_next/data/<buildId>/…json` (buildId from `__NEXT_DATA__`).
- GraphQL: `/graphql` refs, `apollo`/`relay` (replay needs the query body — only via network/render).

**Tier 3/4 — needs a browser**
- Tier 3 CSR: framework root div empty + no SSR list + no hydration array.
- Tier 4 interaction: `role="tab"`/`aria-controls`, sector/fund/region `<select>` filters, "load more" buttons, a search `<input>` with no initial list, cookie/region modal.

**Tier 5 — vision / human**
- Image-only: one large `<img>`/`<picture>` or sprite covering many logos; `<canvas>`/WebGL.
- PDF: `<a href=*.pdf>` near "portfolio"/"fact sheet"/"one-pager".
- Bot wall: `Just a moment…`, `cf-browser-verification`, `__cf_chl_`, `Attention Required`, hCaptcha/reCAPTCHA scripts.

**Cross-cutting**
- F4 lazy images: `loading="lazy"`, empty `src` with `data-src`/`data-lazy` on logo imgs (alt text may still carry names).

## Customer-facing UX — background, progress-message only (decided)

Mechanism selection is **automatic and invisible as a choice**. The customer is not
asked to pick a fetch method. They see **transparency as scan progress**:

```text
"Inspecting how this firm publishes its portfolio…"     (triage)
"Reading the portfolio list…"                           (Tier 1)
"Querying the site's data source…"                      (Tier 2)
"Rendering the page to read its portfolio…"             (Tier 3 headless)
"Navigating the portfolio (filters / scrolling)…"       (Tier 4)
"Searching public sources…"                             (web-search fallback)
```

These ride the scan's existing progress/percentage channel. The customer-opt-in
escalations (deepen / upload-list / provide-source-URL) remain the rungs offered
**only when automation comes up short** — the mechanism routing itself is never a
customer decision.

## Structured rungs always run + trust the firm's own data (revised 2026-06-29)

The deterministic rungs (wp-json CPT + sitemap) were initially gated behind a
low in-HTML yield (`<= 5`) — the assumption being "the scrape already found the
real list." That assumption broke on **General Atlantic**: it server-renders a
*partial, rotating* ~19-company list while its `investment` CPT holds **406**, so
the gate skipped the authoritative source and discovery returned 19. **Fix: the
structured rungs ALWAYS run for a PE firm** (they are browser-free, authoritative,
and additive — deduped against the scrape — so they can only ADD the firm's own
data; cost is 1–2 cheap deterministic probes per scan, fast-pathed on re-scan by
the per-domain cache). The web-search fallback keeps its low-yield gate (it is the
expensive/hallucination-prone rung).

Corollary: **wp-json/sitemap companies are TRUSTED** — they are the firm's own
structured data, so they join `auto_included` and skip the per-company AI
validation that exists to filter web-search/nav-link junk. This also avoids
hundreds of validation calls for large-CPT firms (GA 405, Insight 847).

Also fixed in this pass: a `structured_endpoint` result now reads as
`full_site_list` (was always `partial_site_list` "may be incomplete"), and
img-`alt` context names are normalised apostrophe-safely ("Harry's", not the
`str.title()` artifact "Harry'S").

### Deferred minor name-extraction edge cases (low priority, ~1 row each)

Surfaced during the 2026-06-30 corpus verification; left for a later pass because
each is a single-row cosmetic issue with no clean fix, and AI validation / the
confirm screen absorb them:

- **Very short detail-link slugs.** `warburgpincus.com/investments/aa/` →
  `name_from_url_slug` returns `""` (below the 2-char floor), so the empty-anchor
  path falls back to the shared "Border Green" context label. Special-casing
  2-char slugs would let real junk through; the link is itself likely junk and AI
  validation drops it.
- **Context heading grabbed the wrong element.** One Sun Capital card
  (`/portfolio/clinicalcare/`) yields blob text "Clinical CareServicesFlorida"
  with `context_name="Services"` (wrong) and an unsplittable slug "Clinicalcare",
  so neither the prefix rule nor the slug recovers "Clinical Care". No reliable
  signal to split the blob.

## Pipeline placement

A routine at the front of `DiscoverPortfolio` (or a thin `ClassifyDeliveryStep`
that annotates the company), running on the HTML the existing scrape already pulls
— not a separate fetch pass:

```text
PortfolioScan → DiscoverPortfolio
   ├─ fetch firm HTML (existing curl)
   ├─ TRIAGE(html) → delivery_mechanism + confidence          (new)
   ├─ run ladder starting at routed rung (reordered, reusing existing extractors)
   └─ merge → mechanism-aware verdict + progress messages
```

Design knobs: heuristics-first (regex/DOM signatures) with LLM only for the
ambiguous residue; triage **prunes, never hard-gates**; **cache the classification
per domain** so re-scans skip straight to the proven fast path.

## Task-0 spike result (2026-06-29, n=11 real PE/VC firms)

Classified 11 firms by fetching raw HTML + probing endpoints. **9/11 (82%) need
NO browser.**

| Firm | Mechanism | Tier | Reliable fetch |
|------|-----------|------|----------------|
| Thoma Bravo | A2 Next.js RSC payload (`__next_f`), empty visible DOM | T1 | AI-on-raw-HTML (already ships); names present |
| Silver Lake | A1 anchors + wp-json `portfolio` (175) | T1/T2 | anchors or `/wp-json/wp/v2/portfolio` |
| Warburg Pincus | A1 WordPress server-rendered (~177 links, no CPT exposed) | T1 | parse `/investments/` anchors |
| Francisco Partners | A1 Nuxt server anchors `/investments/{slug}` | T1 | slug names (handled) |
| Summit Partners | A1 server-rendered list `/companies/{slug}` | T1 | parse anchors |
| Vista | CSR/logo-grid shell → wp-json `company` (149) | **T2** | `/wp-json/wp/v2/company` |
| Insight Partners | CSR shell → wp-json `sfcompany` (847*) | **T2** | `/wp-json/wp/v2/sfcompany` |
| General Atlantic | CSR shell → wp-json `investment` (406*) | **T2** | `/wp-json/wp/v2/investment` |
| Alpine Investors | CSR shell → wp-json `our-companies` (66 ✓) | **T2** | `/wp-json/wp/v2/our-companies` |
| Riverside | custom app, portfolio via unknown XHR (static HTML = team only) | T2?/T3 | discover endpoint (render-once) |
| Audax | near-empty shell at `/portfolio`, no portfolio iframe | T3? | fix path / find endpoint, else render |

`*` counts include realized/exited — need a current-vs-realized filter.

### Mid-market / services batch (n=8; the customer-profile segment)

Shore Capital, Webster Equity, Gryphon, Trivest, Wind Point, Halifax, Sun Capital,
Kohlberg. **6/6 reachable firms were WordPress** (WP dominance is even stronger in
mid-market than brand-name). 2 (Webster, Wind Point) refused plain `curl` entirely
(connect failure) — an F1 transport wall our production `curl_cffi` impersonation
likely defeats, so **this spike under-counts reachability**.

| Firm | Mechanism | Tier | Fetch |
|------|-----------|------|-------|
| Gryphon | WP server anchors (71) + wp-json `companies` (75) | T1/T2 | anchors or CPT |
| Sun Capital | WP server anchors (106) + wp-json `post_portfolio` | T1/T2 | anchors or CPT |
| Kohlberg | WP shell (anchors=0) → wp-json `company` (55) | **T2** | CPT |
| Shore Capital | Next.js frontend over WP, some server anchors (23) | T1/T2 | anchors / Next data |
| Trivest | WP, portfolio embedded in `data-fields="{…json…}"` attrs | **T1** | parse data-attrs (no browser) |
| Halifax | WP, server-rendered cards + client-side filter tabs (all in HTML) | **T1** | parse cards |
| Webster | unreachable via plain curl (F1) | ? | needs impersonation |
| Wind Point | unreachable via plain curl (F1) | ? | needs impersonation |

### Residue resolved — both via sitemap (no browser)

- **Riverside** (HubSpot CMS, not WP): `sitemap.xml` enumerates
  `/investment-portfolio/<slug>` for every company → **Tier-1 (E1 sitemap + slug
  names)**. The static page's only embedded JSON was team data — the sitemap is the
  reliable source.
- **Audax** (Rails, `data-controller="portfolios"`; `/portfolio` looked like a
  31 KB shell): `sitemap.xml` lists `/portfolio/<slug>` for every company →
  **Tier-1 (E1 sitemap)**. The shell was a red herring.

### Combined result (n=19; 17 reachable via plain curl)

**0 of 17 reachable firms genuinely required a headless browser.** Every one fell
to a deterministic/plain-GET rung:

```text
   Tier-1 in-HTML (anchors / embedded data / RSC)  ███████████  Thoma Bravo, Silver Lake,
                                                                 Warburg, Francisco, Summit,
                                                                 Trivest, Halifax, Shore
   Tier-1 via SITEMAP enumeration + slug names      ███          Riverside, Audax  (the "hard" ones!)
   Tier-2 wp-json CPT discovery                      ██████       Vista, Insight, GA, Alpine,
                                                                 Kohlberg, Gryphon, Sun Capital
   Needs headless                                    ·            (none in sample)
   Blocked at transport (F1 → needs impersonation)   ██          Webster, Wind Point
```

**Findings that steer the build (revised after both batches):**
1. **Two cheap deterministic rungs cover essentially everything: (a) `wp-json` CPT
   discovery and (b) `sitemap.xml` enumeration.** WordPress-with-CPT dominates
   (11/17 reachable were WP; ~8 exposed a portfolio CPT), and sitemap rescued the
   two non-WP "hard" cases. **Build these two first.**
2. **Headless was needed by 0/17.** It moves from "next big rung" to "speculative
   tail, maybe never" — and if ever built, the Riverside/Audax lesson says
   "**enumerate the sitemap**" or "**render once to discover the endpoint**," not
   "render and scrape the DOM." Strong signal to *not* prioritize `render-site-headless`.
3. **Triage signature rules now empirically grounded:**
   - `wp-content`/`wp-json` present → probe `/wp-json/wp/v2/types`, fetch the
     portfolio-like CPT (observed names: `company`, `companies`, `sfcompany`,
     `investment`, `our-companies`, `portfolio`, `post_portfolio` — heterogeneous,
     so enumerate `/types`, don't hard-code one path).
   - any firm → fetch `sitemap.xml`, filter `/(portfolio|companies|investment[s]?|
     investment-portfolio)/<slug>` → deterministic list + slug names.
   - embedded `data-fields=`/hydration JSON/RSC payload → parse in place (Trivest,
     Thoma Bravo).
4. **Hard caveats:** wp-json `per_page` caps at 100 → paginate on `X-WP-Total`/
   `page` (same discipline as the DynamoDB rule); realized/exited inflate counts
   (Insight 847, GA 406, Silver Lake 175) → filter on status/taxonomy; `wp-json`
   can be disabled (Warburg) → fall back to anchors/sitemap; **use the impersonating
   transport (`curl_cffi`), not plain GET** — Webster/Wind Point blocked plain curl.

## Spikes before committing (ADR inputs)

1. **Empirical distribution** (the next step in this explore): classify a real list
   of PE/VC firms by mechanism (A1…F) → which tiers dominate, how big is the
   true "needs-a-browser" (Tier 3/4) residue, how often is there a hittable Tier-2
   endpoint behind a CSR shell. This sizes which rungs to build first.
2. **How much classifies from first HTML** vs. needs a render to confirm Tier 2/3.
3. **Endpoint-probe hit rate**: of CSR firms, what fraction expose `/wp-json`,
   `__NEXT_DATA__`, `_next/data`, Algolia/CMS keys we can hit directly (Tier-2
   rescue without a browser).

## Known limitation — egress-IP blocking (from live staging verification, 2026-06-29)

Increment 1 (wp-json + sitemap rungs, PR #461) was spot-checked live on the
deployed staging worker:

| Firm | Rung | Local | Staging (deployed) |
|------|------|-------|--------------------|
| Kohlberg | wp-json `company` | 55 | **55 ✅** |
| Riverside | sitemap `/investment-portfolio/<slug>` | 400 | **400 ✅** |
| Audax | sitemap `/portfolio/<slug>` | 165 | **5 (in-HTML only) ⚠️** |

Both rungs are confirmed working end-to-end on the deployed arm64 worker. But
**Audax returned 0 from the sitemap rung on staging despite 165 locally** — the
rung code is correct (re-verified locally), and the worker *can* reach Audax (the
scrape pulled 5 `/portfolio/` anchors), yet `audaxprivateequity.com/sitemap.xml`
yields nothing from the **AWS datacenter egress IP**. Same class as Webster and
Wind Point, which refused even plain curl: **some firms' CDNs (Cloudflare/Akamai)
block or challenge requests from datacenter/AWS IP ranges**, per-site and
sometimes per-path. This is infrastructure-level, NOT a rung defect — the rungs
correctly fail soft, and it affects all our fetch paths (scrape included), not
just these rungs. The local 19-firm harness can't catch it (residential IP); only
a deployed scan can.

Follow-up options (not in this change's current scope):
- **Egress proxy / residential-IP proxy** for the fetch transport so the worker
  presents a non-datacenter IP to CDNs that block AWS ranges. Highest coverage,
  but adds a paid dependency + per-request cost + an SSRF-review of the proxy hop.
- **Stronger TLS impersonation / header profile** — may recover some sites, won't
  beat IP-range blocks.
- **Lean on the existing customer escalations** (upload-list / provide-source-URL)
  for IP-blocked firms — already shipped, zero new infra; the verdict should flag
  "we couldn't reach this firm's site" so the customer is routed there.
Recommend the last as the default and the proxy as a measured future option once
we see how often real customer firms hit this.

## Related, separate

- `render-site-headless` implements the Tier-3/4 engine; this change is the router
  that decides when to invoke it (render becomes a routed rung, not a blind
  escalation).
- `resilient-portfolio-discovery` already does Tier-1 raw-HTML / hydration-JSON
  extraction; this formalizes it into the ordered ladder with explicit routing.
