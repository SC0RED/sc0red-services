# Tasks — Render-the-site headless-render rung

**Status: backlog / not scheduled.** Kept alive as the live home for the deferred
escalation rung. Do not start without an infra review (the reason it was deferred).

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
