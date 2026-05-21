## MODIFIED Requirements

### Requirement: PDF supports per-section page-format overrides

The PDF SHALL default to A4 portrait for every page and SHALL allow specific sections (e.g., the EBITDA tree page) to override the page format using named `@page` rules in `print.css`. Sections without an override use the default. Section breaks SHALL respect:

- `page-break-inside: avoid` on opportunity cards, risk-score rows, and EBITDA outline blocks
- `page-break-before: always` between major sections in the advisory-narrative order: **Cover → Executive Summary → Top Actions → Value Chain → EBITDA → Risk Profile → AI Opportunity Roadmap → Methodology → Back Cover**, when the previous section is short enough that the next would otherwise start mid-page
- No-orphan-headings: a section heading SHALL NOT appear at the bottom of a page with the body content overflowing to the next page

The advisory-narrative order replaces the previous analyst-tool order (Risk → Opportunities → EBITDA → Value Chain) so that the printed report reads in the same flow as the on-screen analysis page in the rebranded sc0red Advisory product.

#### Scenario: EBITDA tree page renders on a wider page format

- **WHEN** the EBITDA tree section is rendered as part of the PDF
- **THEN** that section's pages use the `ebitda-page` named `@page` rule (A3 landscape)
- **AND** the surrounding pages (cover, executive summary, top actions, value chain, risk profile, opportunities, methodology, back cover) remain A4 portrait

#### Scenario: PDF section order matches the advisory narrative

- **WHEN** an analysis with full data is rendered as a PDF
- **THEN** the section order is: Cover, Executive Summary, Top Actions, Value Chain, EBITDA, Risk Profile, AI Opportunity Roadmap, Methodology Appendix, Back Cover
- **AND** the order matches the on-screen analysis page section order

#### Scenario: Multi-page PDF has a footer on every page

- **WHEN** a generated PDF is two or more pages long
- **THEN** every page after the cover renders the footer template with the page number and total pages
- **AND** the footer text matches the format "Page X of Y · sc0red.com"

#### Scenario: Cover page has no running header

- **WHEN** the PDF cover page is rendered
- **THEN** the page does not show the running header that appears on subsequent pages
