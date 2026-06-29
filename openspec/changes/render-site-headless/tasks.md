# Tasks — Render-the-site headless-render rung

**Status: backlog / not scheduled — DEPRIORITIZED.** A Task-0 spike in
`adaptive-portfolio-discovery` (n=19 PE/VC firms) found **0/17 reachable firms
needed a headless browser** — `wp-json` CPT discovery + `sitemap.xml` enumeration +
in-HTML extraction covered everything. Do not schedule render until
`adaptive-portfolio-discovery` ships and real traffic surfaces firms those cheaper
rungs miss. If ever built, the lesson is "render once to discover the endpoint /
read the sitemap," not "render and scrape the DOM." Still needs an infra review.

- [ ] 0. Infra spike/decision: chromium-in-Lambda (size, cold-start, 15-min cap)
  vs. separate render service vs. managed browser API. Output: an ADR.
- [ ] 1. Render engine: load URL, await client-side render, return rendered HTML;
  feed the existing `extract_companies_from_scrape` + merge path.
- [ ] 2. Apply the `assert_public_url` SSRF guard to the headless fetch (and any
  sub-resource loads).
- [ ] 3. Step + factory + worker dispatch + `POST /api/scan/{id}/render`
  (mirror the `deepen` / `source-url` additive-merge path); tag source `render`.
- [ ] 4. Flip `render_site` to a live action in `DiscoveryVerdictBanner`
  (remove the "soon" disabled state); customer-opt-in with cost framing.
- [ ] 5. Tests (engine, SSRF on render, additive merge, fail-soft) + E2E + PR.
