## ADDED Requirements

### Requirement: Heuristic discovery has no hardcoded company-count cap

The heuristic portfolio discovery path SHALL return every candidate company it identifies within a scraped page, without truncating to a fixed maximum. Candidate filtering remains governed by link quality (external domain, not social, not a generic CTA without a derivable name) — not by arbitrary count.

#### Scenario: Heuristic returns more than 30 candidates on a large portfolio page

- **WHEN** the heuristic path processes a page whose HTML contains 70 external portfolio anchor tags (each representing a distinct operating company, e.g., perotjain.com/portfolio/)
- **THEN** the returned candidate list contains > 30 companies — not silently truncated to 30

### Requirement: Name derivation falls back to img src filename when alt is empty

When an anchor's text is a generic CTA (e.g., "LEARN MORE") and the surrounding card has no heading and no non-empty `<img alt>`, the system SHALL attempt to derive the company name from the nearest `<img src>` filename.

#### Scenario: Card with empty alt still produces a company name

- **WHEN** processing an anchor `<a>LEARN MORE</a>` whose sibling `<img alt="" src=".../endurancelift.png">` has an empty alt
- **THEN** the heuristic derives the name "Endurance Lift" (or equivalent title-cased form) from the filename and does not drop the anchor

#### Scenario: Filename with separators is tokenized

- **WHEN** the img src ends with `/access-healthcare-logo.png`
- **THEN** the `-logo` suffix is stripped and the result is "Access Healthcare"

### Requirement: Name derivation falls back to URL domain when all HTML sources yield nothing

When an anchor has a CTA-like text, an empty/missing alt, no heading in the card, and no useful img filename, the system SHALL derive the name from the anchor's target URL hostname (stripping `www.` and the TLD) rather than dropping the candidate.

#### Scenario: Domain-only name when HTML has no signal

- **WHEN** processing an anchor `<a href="https://www.foobar.com/">LEARN MORE</a>` whose surrounding card contains no heading, no img alt, and no usable img src
- **THEN** the heuristic derives the name "Foobar" from the hostname and keeps the candidate; the AI validation step and/or user confirmation step is responsible for final name quality

### Requirement: AI extraction receives enough page content to cover large portfolios

The AI-based extraction path SHALL send enough scraped page content and enough link entries to the LLM that a portfolio page with 70+ companies is not truncated mid-list.

#### Scenario: Page-text budget accommodates 70-company pages

- **WHEN** the discovery step invokes `run_structured_ai_call` for portfolio extraction
- **THEN** the user prompt includes up to 30 000 characters of page text (up from 8 000) and up to 10 000 characters of link text (up from 3 000) covering the first 300 anchors (up from 100)
