# Tasks — Adaptive portfolio discovery (classifier + routing)

**Status: backlog / not scheduled.** Task 0 (spike) is **done** — see design.md.
Build order below reflects what the spike proved: the two deterministic rungs
(wp-json CPT + sitemap) carry nearly all firms; headless is a speculative tail.

- [x] 0. **Spike: empirical mechanism distribution.** Done (n=19 PE/VC firms).
  Result: 0/17 reachable firms needed a browser; `wp-json` CPT discovery + `sitemap`
  enumeration + in-HTML extraction covered everything. Full table in design.md.

- [x] 1. **`wp-json` CPT discovery rung** (highest ROI). Done (PR #461). Probe
  `/wp-json/wp/v2/types`, pick the portfolio-like CPT, fetch paginated, map to
  {name, url}. SSRF-guarded; via `curl_cffi`. Verified live: Kohlberg 55.
- [x] 2. **`sitemap.xml` enumeration rung.** Done (PR #461). Fetch sitemap(s),
  follow an index one level, filter `/<section>/<slug>`, derive names via the
  shared `name_from_url_slug`. Verified live: Riverside 400.
- [ ] 3. **Triage routine.** Heuristic signature detection on the first fetched HTML
  → `delivery_mechanism` + confidence (catalog in design.md); LLM only for the
  ambiguous residue. Routes/prunes the ladder; never hard-gates.
- [ ] 4. **Self-classifying escalation ladder.** Order: in-HTML parse (anchors /
  hydration JSON / data-attrs / RSC) → wp-json → sitemap → web-search → render
  (tail). Early-exit on sufficient yield; triage reorders.
- [ ] 5. **Mechanism-aware verdict.** Thin on static HTML → "complete, stop"; thin
  on CSR shell → "escalate to endpoint/sitemap." Gates costly rungs.
- [ ] 6. **Realized-vs-current filter.** wp-json counts include exited companies
  (Insight 847, GA 406, Silver Lake 175) — filter on status/taxonomy.
- [ ] 7. **Background progress messages** on the scan channel — no customer routing
  choice.
- [ ] 8. **Per-domain classification cache** so re-scans skip triage → proven path.
- [ ] 9. Tests (signature detection, both rungs incl. pagination, routing,
  mechanism-aware verdict, fail-soft, cache) + E2E + PR.

- [ ] 10. **Egress-IP-blocking mitigation** (surfaced by live staging verification —
  see design.md "Known limitation"). Audax/Webster/Wind Point are unreachable from
  the AWS datacenter egress IP (their CDNs block datacenter ranges). Default:
  verdict should flag "couldn't reach the firm's site" and route to upload /
  source-URL (already shipped). Future option: a residential/egress proxy for the
  fetch transport (paid + SSRF review). Measure real-customer hit rate first.

- [ ] (deferred / speculative) Integrate `render-site-headless` as the last
  router-selected rung — only if real traffic surfaces firms the rungs above miss.
  The spike found none; do not schedule render until this change proves a gap.
