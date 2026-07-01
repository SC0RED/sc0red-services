# portfolio-discovery-routing Specification

## Purpose
Makes portfolio discovery delivery-mechanism-aware. As shipped, discovery ALWAYS runs the deterministic structured rungs (WordPress `wp-json` portfolio CPT + `sitemap` enumeration) for a PE firm alongside the in-HTML scrape, then classifies *how* the firm publishes its portfolio **post-hoc** — from which path actually produced the list — and interprets a thin/empty result through that mechanism instead of guessing. The classification is surfaced as automatic background progress, never a customer-facing routing choice. (A pre-fetch *triage* that classifies from the first HTML and reorders/prunes the ladder before fetching is a deferred optimization; the always-run-rungs design covered the verification corpus without it.)

## Requirements
### Requirement: Discovery classifies the firm's portfolio delivery mechanism

Portfolio discovery SHALL classify *how* a firm publishes its portfolio (e.g.
`static_listing`, `structured_endpoint`, `embedded_json`, `ai_extracted`,
`opaque_shell`, `no_portfolio_found`, `unreachable`) from which discovery path
produced companies. The deterministic structured rungs (wp-json CPT + sitemap)
SHALL run for a PE firm regardless of the in-HTML yield and contribute additively
(deduped against the scrape), so an authoritative structured source is never
skipped just because the page also server-renders a partial list. The
classification MUST be advisory — it informs the verdict and messaging — and MUST
NOT hard-gate: an inconclusive path still falls through the additive rungs and the
web-search fallback rather than failing the scan.

#### Scenario: Client-side-rendered shell is recovered by a structured rung
- **WHEN** the fetched HTML is an empty framework shell with no server-rendered
  list and no embedded portfolio payload
- **THEN** the always-run structured rungs (wp-json CPT / sitemap) recover the
  list the plain scrape missed, and the result is classified `structured_endpoint`
  (rather than returning the empty server-side scrape)

#### Scenario: Static server-rendered list is not needlessly escalated
- **WHEN** the firm serves a substantial server-rendered portfolio list and discovery
  extracts it
- **THEN** discovery treats the result as complete and does NOT invoke the costly
  web-search fallback to look for data the mechanism shows is not hidden

### Requirement: A thin result is interpreted through the delivery mechanism

The discovery verdict SHALL incorporate the classified delivery mechanism when
deciding whether a low company count means "complete" or "missed data." A result
carried by an authoritative structured rung SHALL read as a complete list
(`full_site_list`); a thin result on a static-HTML firm SHALL be treated as a
complete (small) portfolio; and an empty result on a client-side-rendered or
unreachable firm SHALL be explained by the mechanism (e.g. `opaque_shell` /
`unreachable`) and route the customer to the escalations below.

#### Scenario: Structured-rung result reads as complete
- **WHEN** a structured rung (wp-json CPT / sitemap) enumerated the firm's
  portfolio
- **THEN** the verdict is `full_site_list` (complete), even if the page also
  server-rendered only a partial subset, and no "may be incomplete" caveat is shown

#### Scenario: Empty count on a client-side-rendered firm is explained
- **WHEN** the firm is classified `opaque_shell` (a skeletal shell the scrape and
  rungs could not read) or `unreachable`
- **THEN** the verdict explains the mechanism and points the customer at the
  escalations (search deeper / upload a list / provide a source URL)

### Requirement: Discovery surfaces mechanism work as background progress

Mechanism handling SHALL be automatic and MUST NOT require a customer choice.
Discovery SHALL surface the work as progress messages on the scan's existing
progress channel (e.g. "Reading the firm's portfolio page…", "Querying the firm's
data sources…", "Searching public sources…"). Customer-opt-in escalations (deepen
/ upload-list / provide-source-URL) remain available only when automated discovery
comes up short.

#### Scenario: Customer sees progress, not a routing decision
- **WHEN** discovery runs its rungs and classifies the mechanism
- **THEN** the customer sees a human-readable progress message describing the
  current step, and is never prompted to choose a fetch technique
