## ADDED Requirements

### Requirement: Deterministic extraction of embedded company records

Portfolio discovery SHALL deterministically parse structured company records embedded as JSON in a site's inline `<script>` content, extracting each company's name and slug, without relying on AI extraction. Parsing SHALL handle both plain JSON (`"name":"X","slug":"x"`) and escaped/stringified JSON (`\"name\":\"X\",\"slug\":\"x\"`), and SHALL run over the full script content (not the AI-prompt-truncated copy) so the complete list is recovered.

#### Scenario: SSR hydration island with structured company records

- **WHEN** a portfolio page embeds company records as JSON in a `<script>` (e.g. `{"name":"Calabrio","slug":"calabrio", …}`) and the visible DOM has no company anchors
- **THEN** every company record is extracted as a `(name, slug)` pair
- **AND** the count is not limited by the AI-prompt truncation budget

#### Scenario: Noise fields are not mistaken for companies

- **WHEN** the embedded JSON also contains nested objects with a `name` key but no adjacent `slug` (e.g. a logo asset `{"alt":"…","name":"…"}` or `searchableNormalized:{"name":"…"}`)
- **THEN** those are NOT extracted as companies — only records with an adjacent `name`+`slug` pair qualify

#### Scenario: Site without structured embedded records

- **WHEN** a portfolio page has no `name`+`slug` JSON records
- **THEN** deterministic extraction yields nothing and discovery proceeds via the existing heuristic-link and AI-extraction paths unchanged

### Requirement: Scannable candidate URLs from detail pages

For each embedded company record, discovery SHALL form a candidate URL from the firm's own per-company detail page derived from the slug (the listing page path plus the slug), so the existing per-company scan URL-resolution step can resolve the company's real website. These candidates SHALL enter the existing validation tier (never auto-included without validation).

#### Scenario: Candidate URL built from slug

- **WHEN** a record `{"name":"Calabrio","slug":"calabrio"}` is extracted from the listing page `https://www.thomabravo.com/portfolio`
- **THEN** the candidate URL is the firm detail page `https://www.thomabravo.com/portfolio/calabrio`
- **AND** the candidate is added to the validation tier alongside heuristic/AI candidates, deduplicated by URL

#### Scenario: Detail page resolves to the real company site

- **WHEN** the per-company scan processes a detail-page candidate URL that links out to the company's own website
- **THEN** the existing URL-resolution step resolves and scans the real company site
