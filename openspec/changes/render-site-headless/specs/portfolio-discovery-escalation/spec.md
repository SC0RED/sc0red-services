# Spec — portfolio-discovery-escalation (render-site rung)

## ADDED Requirements

### Requirement: Headless render is an executable escalation rung

The "render the site" escalation SHALL load the firm URL in a headless browser,
wait for client-side rendering, and extract the portfolio from the rendered DOM —
recovering companies a server-side scrape cannot see. It SHALL remain
customer-opt-in (presented with clear cost framing, executed only on explicit
selection) and additive (it augments the existing list, never destroys it).

When shipped, this supersedes the prior "deferred opt-in rung" behaviour (under
which selecting render-site informed the customer it was not yet available);
that deferred behaviour remains correct until this rung is built.

#### Scenario: Customer selects render-the-site on a client-side-rendered firm
- **WHEN** discovery returns a thin/empty list for a firm that renders its
  portfolio client-side, and the customer selects "render the site"
- **THEN** the firm page is loaded in a headless browser, the post-render DOM is
  extracted, and the newly-found companies are merged into the awaiting-
  confirmation list (entering the needs-validation tier, tagged source `render`)

#### Scenario: Render targets are SSRF-guarded
- **WHEN** the headless render fetches the firm URL (and any sub-resources)
- **THEN** the same public-URL guard that protects the server-side scraper
  applies, refusing private/loopback/link-local/metadata targets

#### Scenario: Render failure is fail-soft
- **WHEN** the headless render fails or times out
- **THEN** the prior awaiting-confirmation list is preserved and the customer is
  pointed at deeper-search / upload, never left with an empty or errored scan
