# Render-the-site headless-render discovery rung

## Why

The discovery escalation ladder (`customer-guided-portfolio-discovery`) defined
three rungs: **Search deeper** (web search), **Upload a list**, and **Render the
site** (headless browser). The first two shipped; **Render the site was
deliberately deferred to its own change** — the `render_site` action is already
surfaced in the UI as a disabled "soon" affordance, and selecting it tells the
customer it isn't available yet and points to deeper-search / upload.

This change is the live home for that deferred rung. It is **not yet scheduled** —
it carries the context so the work is referable and explorable later, not lost in
the archived parent changes.

The gap it eventually closes: some firms render their portfolio entirely
client-side (JS builds the list in the browser after load) or behind
interactions our server-side `curl_cffi` scrape can't trigger. `partial_site_list`
/ `web_search_subset` verdicts flag these today, but the only complete recovery is
the customer uploading a list or providing a source URL. A headless render would
let us read the post-load DOM directly.

## What changes (when built)

- A headless-render engine (Playwright / chromium) that loads the firm URL,
  waits for client-side render, and extracts the portfolio from the rendered DOM
  — reusing the existing `extract_companies_from_scrape` + merge/verdict path.
- The `render_site` escalation action becomes **live**: selecting it dispatches a
  render-and-merge (mirroring the `deepen` / `source-url` additive escalations),
  re-entering the discovery loop.
- Candidates enter the existing `needs_validation` tier (model/DOM-derived, not
  asserted), tagged with a `render` source for provenance.

## Open questions (to resolve when scheduled)

- **Runtime/infra**: chromium-in-Lambda (layer/container size, cold-start, the
  15-min limit) vs. a separate render service vs. a managed browser API. Needs an
  infra review — this is the reason it was deferred.
- **SSRF**: the same guard (`assert_public_url`, see `harden-scraper-ssrf`) must
  cover the headless fetch, including any sub-resource loads the browser makes.
- **Cost/latency framing**: it's the most expensive rung; keep it customer-opt-in
  with clear cost messaging (already the UX intent).

## Impact

- Affected specs: `portfolio-discovery-escalation` (render-site moves from
  "deferred opt-in" to executable).
- Affected code (when built): a new render engine + step/factory, the worker
  dispatch + `POST /api/scan/{id}/render` (mirroring deepen/source-url), and
  flipping `render_site` to a live action in `DiscoveryVerdictBanner`.
- Status: **backlog / not scheduled.** Kept alive intentionally per product
  direction; supersedes the deferred Phase 3 notes in the now-archived
  `customer-guided-portfolio-discovery`.
