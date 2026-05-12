## MODIFIED Requirements

### Requirement: PDF supports per-section page-format overrides

The PDF SHALL default to A4 portrait for every page and SHALL allow specific sections (e.g., the EBITDA tree page) to override the page format using named `@page` rules in `print.css`. Sections without an override use the default. Section breaks SHALL respect:

- `page-break-inside: avoid` on opportunity cards, risk-score rows, EBITDA outline blocks, and **strategy-map perspective rows when the strategy map is present**
- `page-break-before: always` between major sections in the advisory-narrative order: **Cover → Executive Summary → Strategy Map (when present) → Top Actions → Value Chain → EBITDA → Risk Profile → AI Opportunity Roadmap → Methodology → Back Cover**, when the previous section is short enough that the next would otherwise start mid-page
- No-orphan-headings: a section heading SHALL NOT appear at the bottom of a page with the body content overflowing to the next page

The Strategy Map section is conditional — included when the analysis has a persisted strategy map, omitted otherwise. Strategy-map persistence is now driven by user-explicit on-demand generation (per the `ai-strategy-map` capability spec), so analyses without a persisted map are the default-new state, not a legacy edge case. The PDF includes whatever's persisted at export time; the export does NOT trigger generation.

#### Scenario: PDF includes the strategy map when persisted

- **WHEN** an analysis with full data and a populated `strategyMap` is rendered as a PDF
- **THEN** the section order is: Cover, Executive Summary, **Strategy Map**, Top Actions, Value Chain, EBITDA, Risk Profile, AI Opportunity Roadmap, Methodology Appendix, Back Cover
- **AND** the order matches the on-screen analysis page section order at the time of export

#### Scenario: Analysis without a strategy map omits the section

- **WHEN** an analysis without a persisted `strategyMap` is rendered as a PDF (whether it's a fresh analysis where the user hasn't generated yet, or a re-analysed one where the previous map was invalidated)
- **THEN** the Strategy Map section is omitted entirely from the PDF
- **AND** the section order continues with Executive Summary → Top Actions
- **AND** no placeholder, "generate from app" prompt, or empty header appears

#### Scenario: EBITDA tree page renders on a wider page format

- **WHEN** the EBITDA tree section is rendered as part of the PDF
- **THEN** that section's pages use the `ebitda-page` named `@page` rule (A3 landscape)
- **AND** the surrounding pages remain A4 portrait

#### Scenario: Strategy-map perspective rows survive page breaks

- **WHEN** the Strategy Map section is rendered (only applies when the map is persisted) and a perspective row would otherwise split across pages
- **THEN** the row is kept intact via `page-break-inside: avoid`
- **AND** the row starts on a fresh page when needed
