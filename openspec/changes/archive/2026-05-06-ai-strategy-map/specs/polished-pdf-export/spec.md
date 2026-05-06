## MODIFIED Requirements

### Requirement: PDF supports per-section page-format overrides

The PDF SHALL default to A4 portrait for every page and SHALL allow specific sections (e.g., the EBITDA tree page) to override the page format using named `@page` rules in `print.css`. Sections without an override use the default. Section breaks SHALL respect:

- `page-break-inside: avoid` on opportunity cards, risk-score rows, EBITDA outline blocks, and **strategy-map perspective rows**
- `page-break-before: always` between major sections in the advisory-narrative order: **Cover → Executive Summary → Strategy Map → Top Actions → Value Chain → EBITDA → Risk Profile → AI Opportunity Roadmap → Methodology → Back Cover**, when the previous section is short enough that the next would otherwise start mid-page
- No-orphan-headings: a section heading SHALL NOT appear at the bottom of a page with the body content overflowing to the next page

The Strategy Map section is added as the first content section after the Executive Summary, mirroring the on-screen analysis page placement at position 3 (after header + overview cards). The advisory-narrative order is otherwise unchanged from the order established by the `rename-janus-to-vector-advisory` change.

#### Scenario: PDF section order includes the strategy map

- **WHEN** an analysis with full data and a populated `strategyMap` is rendered as a PDF
- **THEN** the section order is: Cover, Executive Summary, **Strategy Map**, Top Actions, Value Chain, EBITDA, Risk Profile, AI Opportunity Roadmap, Methodology Appendix, Back Cover
- **AND** the order matches the on-screen analysis page section order

#### Scenario: Analysis without a strategy map omits the section

- **WHEN** a legacy analysis without `strategyMap` is rendered as a PDF
- **THEN** the Strategy Map section is omitted entirely
- **AND** the section order continues with Executive Summary → Top Actions

#### Scenario: EBITDA tree page renders on a wider page format

- **WHEN** the EBITDA tree section is rendered as part of the PDF
- **THEN** that section's pages use the `ebitda-page` named `@page` rule (A3 landscape)
- **AND** the surrounding pages (cover, executive summary, strategy map, top actions, value chain, risk profile, opportunities, methodology, back cover) remain A4 portrait

#### Scenario: Strategy-map perspective rows survive page breaks

- **WHEN** the Strategy Map section is rendered and a perspective row would otherwise split across pages
- **THEN** the row is kept intact via `page-break-inside: avoid`
- **AND** the row starts on a fresh page when needed

#### Scenario: Multi-page PDF has a footer on every page

- **WHEN** a generated PDF is two or more pages long
- **THEN** every page after the cover renders the footer template with the page number and total pages
- **AND** the footer text matches the format "Page X of Y · sc0red.com"

#### Scenario: Cover page has no running header

- **WHEN** the PDF cover page is rendered
- **THEN** the page does not show the running header that appears on subsequent pages
