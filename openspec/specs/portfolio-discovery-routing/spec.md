# portfolio-discovery-routing Specification

## Purpose
Makes portfolio discovery delivery-mechanism-aware: a fast triage on the first fetched HTML classifies *how* a firm publishes its portfolio (framework / hydration-payload / data-endpoint / bot-wall / image-only signatures), advisorily routes the fetch to the appropriate technique, and interprets a thin result through that mechanism instead of guessing — all surfaced as automatic background progress rather than a customer-facing routing choice.
## Requirements
### Requirement: Discovery classifies the firm's portfolio delivery mechanism

Portfolio discovery SHALL classify *how* a firm publishes its portfolio (from the
fetched HTML's framework / hydration-payload / data-endpoint / bot-wall /
image-only signatures) and use that classification to route the fetch to the
appropriate technique. The classification MUST be advisory (it reorders/prunes the
fetch ladder) and MUST NOT hard-gate — an inconclusive or wrong classification
still falls through to the escalation ladder rather than failing the scan.

#### Scenario: Client-side-rendered shell is routed past plain scrape
- **WHEN** the fetched HTML is an empty framework shell with no server-rendered
  list and no embedded portfolio payload
- **THEN** discovery routes to a data-endpoint probe and/or headless render
  (rather than returning the empty server-side scrape as the result)

#### Scenario: Static server-rendered list is not needlessly escalated
- **WHEN** the firm serves a complete server-rendered portfolio list and discovery
  extracts it
- **THEN** discovery treats the result as complete and does NOT invoke an expensive
  rung (headless render) to look for data that the mechanism shows is not hidden

### Requirement: A thin result is interpreted through the delivery mechanism

The discovery verdict SHALL incorporate the classified delivery mechanism when
deciding whether a low company count means "complete" or "missed data." A thin
result on a static-HTML firm SHALL be treated as a complete (small) portfolio; a
thin result on a client-side-rendered or interaction-gated firm SHALL trigger
escalation to a mechanism-appropriate rung.

#### Scenario: Thin count on a static firm stops cleanly
- **WHEN** the firm is classified static server-rendered HTML and discovery finds a
  small number of companies
- **THEN** the verdict is "complete list" and no further automated escalation runs

#### Scenario: Empty count on a rendered firm escalates
- **WHEN** the firm is classified as client-side-rendered and discovery's plain
  scrape finds zero companies
- **THEN** the verdict flags missed data and escalation to the routed rung
  (endpoint probe / headless render) is invoked

### Requirement: Discovery surfaces mechanism work as background progress

The fetch-mechanism selection SHALL be automatic and MUST NOT require a customer
choice. Discovery SHALL surface the work as progress messages on the scan's
existing progress channel (e.g. "Inspecting how this firm publishes its
portfolio…", "Rendering the page to read its portfolio…"). Customer-opt-in
escalations (deepen / upload-list / provide-source-URL) remain available only when
automated discovery comes up short.

#### Scenario: Customer sees progress, not a routing decision
- **WHEN** discovery classifies the mechanism and routes the fetch
- **THEN** the customer sees a human-readable progress message describing the
  current step, and is never prompted to choose a fetch technique
