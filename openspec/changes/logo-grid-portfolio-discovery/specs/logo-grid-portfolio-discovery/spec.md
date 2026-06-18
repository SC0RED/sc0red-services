## ADDED Requirements

### Requirement: Extract company names from logo-image alt text

The scraper SHALL extract portfolio company names from logo `<img>` `alt` text on a firm's portfolio page — handling at least "Logo of [the] [software] company {Name}" and "{Name} logo" forms — cleaning boilerplate ("logo of", "company", trailing punctuation), bounding by the existing name-length limits, excluding the firm's own logo, and deduplicating. These names are surfaced additively (a new field) without disturbing existing scrape output.

#### Scenario: Logo grid with names in alt text

- **WHEN** a portfolio page renders companies as logo images with `alt="Logo of software company Jamf"` (no links, no detail pages)
- **THEN** "Jamf" is extracted as a company name
- **AND** the firm's own logo (`alt="Vista logo"`) is not included

#### Scenario: Site without a logo grid

- **WHEN** a page has no logo-style `alt` text
- **THEN** no names are extracted and discovery proceeds via the existing paths unchanged

### Requirement: Seed the web-search fallback with on-site names

When the site path yields no companies but logo-grid names were found, the web-search fallback SHALL be seeded with those names and asked to return each company's official website URL (and may add other current holdings). When no on-site names are available, the fallback SHALL request comprehensive current holdings rather than a minimal shortlist. Fallback candidates remain in the validation tier.

#### Scenario: Logo-grid firm with no on-site URLs

- **WHEN** the site path yields 0 companies but 68 logo-grid names were extracted
- **THEN** the grounded web-search call is seeded with those names and returns name+URL candidates for them
- **AND** the candidates enter the validation tier (not auto-included)

#### Scenario: Opaque firm with no logo grid and no site companies

- **WHEN** the site path yields 0 companies and no logo-grid names exist
- **THEN** the web-search fallback runs in comprehensive mode (broad current-holdings recall), not a conservative shortlist

#### Scenario: Healthy site is unaffected

- **WHEN** the site path already yields companies (embedded JSON or anchor links)
- **THEN** the web-search fallback does not fire and seeding has no effect
