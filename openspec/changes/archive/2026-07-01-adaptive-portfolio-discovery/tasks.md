# Tasks — Adaptive portfolio discovery (classifier + routing)

**Status: SHIPPED to production 2026-06-30, archived 2026-07-01.** Delivered via
PRs #460–#473; live in dev/testing/production; smoke-tested on dev + testing (GA
19→~419, Insight 847, Kohlberg 55 read `full_site_list`; names clean). The
checkboxes below predate delivery and are left as-authored — final state:
- Tasks 1, 2 (wp-json + sitemap rungs), 5 (mechanism-aware verdict), 6 (realized
  filter), 7 (background progress), 8 (per-domain cache), 9 (tests + E2E) — **DONE**.
- Tasks 3, 4 (a separate triage routine + self-classifying ladder) — **superseded**:
  rather than a pre-fetch classifier, the shipped design ALWAYS runs the deterministic
  structured rungs for a PE firm (additive, deduped) and classifies the mechanism
  *post-hoc* from which path bore fruit. Simpler and covers the spike corpus; no
  separate triage router was needed.
- Task 10 (egress-IP mitigation) — **deferred** (measure-first; the verdict already
  routes IP-blocked firms to upload/source-URL). Carry forward as future work.

Original build order below reflects what the spike proved: the two deterministic
rungs (wp-json CPT + sitemap) carry nearly all firms; headless is a speculative tail.

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
