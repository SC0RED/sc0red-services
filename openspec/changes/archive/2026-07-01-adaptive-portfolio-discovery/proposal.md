# Adaptive portfolio discovery — classify the delivery mechanism, then route the fetch

## Why

Today portfolio discovery is effectively **"try several extractors and merge"** —
crawl portfolio paths, filter anchors, parse hydration JSON, read logo grids, and
fall back to web search. It works, but it is **blind**: it doesn't know *how a
given firm actually publishes its portfolio*, so it can't tell the difference
between two situations that look identical (a thin result):

- a genuinely small firm whose **whole** portfolio is 3 companies, and
- a firm that renders its list **client-side** where we caught an empty shell and
  missed 80 companies.

The verdict layer (`partial_site_list`, `web_search_subset`) *guesses* at this.
That guess decides whether we burn an expensive escalation (web search today,
headless render later) — so the guess being wrong is costly in both directions:
we render firms that didn't need it, and we stop short on firms that had hidden
data.

The fix is to make discovery **delivery-mechanism-aware**: a fast triage on the
first fetched HTML classifies *how* the firm serves its portfolio, which then
**routes** the fetch to the right technique (plain parse / data-endpoint probe /
headless render / drive-the-page / vision / external) and **explains** a thin
result instead of guessing at it.

## What changes (when built)

Ordering reflects the Task-0 spike (n=19 firms — see design.md): **0/17 reachable
firms needed a headless browser; two cheap deterministic rungs covered nearly
everything.** So the build leads with those, not with rendering.

- **Two new deterministic rungs (the highest-ROI work):**
  - **`wp-json` CPT discovery** — probe `/wp-json/wp/v2/types`, fetch the
    portfolio-like custom-post-type (`company`/`investment`/`portfolio`/…),
    paginate on `X-WP-Total`. Rescued ~8/17 firms, including ones that looked like
    client-side-rendered shells.
  - **`sitemap.xml` enumeration** — filter `/(portfolio|companies|investments|
    investment-portfolio)/<slug>` → deterministic list + slug names. Rescued the
    two "hardest" (non-WP) firms with no browser.
- A **triage** step reads the already-fetched HTML for delivery-mechanism
  signatures (framework, hydration payload, wp-json/sitemap presence, bot walls,
  image-only lists) → `delivery_mechanism` + confidence.
- Discovery becomes an **ordered, self-classifying escalation ladder** (cheapest
  deterministic first → endpoint/sitemap → … → render as a *speculative tail*),
  where the triage **prunes/reorders** (it optimizes, never hard-gates — a wrong
  guess is still caught by the ladder).
- The **verdict becomes mechanism-aware**: thin on a "static HTML" firm → *small,
  stop*; thin on a "CSR shell" → *missed data, escalate to endpoint/sitemap first*.
- The customer sees **background progress messages** ("Inspecting how this firm
  publishes its portfolio…", "Querying the site's data source…") — not a routing
  choice.
- Per-domain **classification cache** so a re-scan skips triage → proven fast path.
- Use the **impersonating transport** (`curl_cffi`) for all probes — plain GET was
  blocked by 2/19 firms.

## Relationship to other changes

- **`render-site-headless`** is **demoted to a speculative tail.** The Task-0
  spike found 0/17 reachable firms needed it — the wp-json + sitemap rungs plus
  in-HTML extraction covered everything. It stays the router-selected *last* rung
  (invoked only when the mechanism proves hidden data AND the deterministic rungs
  came up empty), and if ever built the lesson is "render once to *discover the
  endpoint / read the sitemap*," not "render and scrape the DOM." This change
  should ship and prove its value **before** any render work is scheduled.
- Builds on `resilient-portfolio-discovery` (raw-HTML / hydration-JSON extraction)
  and `customer-guided-portfolio-discovery` (the deepen / upload / source-url
  escalations remain the customer-opt-in rungs for when automation comes up short).

## Open questions (to resolve when scheduled)

- **Triage engine**: deterministic heuristics (framework/CDN/payload signatures)
  vs. an LLM judgment for the ambiguous residue. Likely heuristics-first, LLM only
  when signatures are inconclusive.
- **How much can be classified from the first HTML alone** vs. needing a render to
  confirm the deeper tiers (the classify-needs-fetch chicken-and-egg).
- **Empirical distribution**: across real PE/VC firms, how common is each
  mechanism? Drives which rungs are worth building first (a spike — see design.md).

## Impact

- Affected specs: new `portfolio-discovery-routing` capability; `render-site` moves
  from "customer-opt-in escalation" to "router-selected rung."
- Affected code (when built): a triage routine in `DiscoverPortfolio`, a strategy
  selector over the existing extractors, mechanism-aware verdict, scan progress
  messages, per-domain cache.
- Status: **backlog / not scheduled.** Capturing the model + the signature catalog
  so the work is referable. Needs the empirical spike before sequencing.
