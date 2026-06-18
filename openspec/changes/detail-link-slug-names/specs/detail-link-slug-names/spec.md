## ADDED Requirements

### Requirement: Derive company names from detail-page slugs

When the heuristic link filter encounters an internal portfolio detail link (a same-domain URL whose path contains a portfolio segment such as `/portfolio/`, `/companies/`, or `/investments/` followed by a slug) and the anchor text is unusable as a company name — too long, a generic call-to-action, or empty — the company name SHALL be derived from the URL slug (the last path segment, title-cased). The detail-page URL remains the candidate URL. When the anchor text already is a usable in-bounds company name, it SHALL be used unchanged.

#### Scenario: Descriptive anchor text, name in the slug

- **WHEN** a portfolio page links `/investments/8x8` with anchor text "Integrated cloud communications platform for…" (longer than the name limit)
- **THEN** the candidate name is derived from the slug ("8x8")
- **AND** the candidate URL is the detail page `https://firm.com/investments/8x8`

#### Scenario: Slug with separators

- **WHEN** the detail link is `/investments/aeries-software` with descriptive anchor text
- **THEN** the slug is title-cased to "Aeries Software"

#### Scenario: Clean anchor text is preserved

- **WHEN** a portfolio link has a short, valid company name as its anchor text (e.g. "Acme Corp")
- **THEN** that anchor text is used as the name (slug derivation does not override it)

#### Scenario: Non-detail same-domain links are unaffected

- **WHEN** a same-domain link is not a portfolio detail link (e.g. the listing page `/investments` itself, or `/about`)
- **THEN** it is handled by the existing filter (not turned into a candidate via slug derivation)
