## ADDED Requirements

### Requirement: Confidence-based result merging
Discovery results from the heuristic and AI paths SHALL be merged using URL domain matching. Companies found by both paths (intersection) SHALL be auto-included. Companies found by only one path (remainder) SHALL be validated by AI.

#### Scenario: Company in both paths
- **WHEN** heuristic finds `{name: "Stripe", url: "https://stripe.com"}` and AI finds `{name: "Stripe Inc", url: "https://www.stripe.com"}`
- **THEN** the company is auto-included (URL domains match after normalization)

#### Scenario: Company in one path only
- **WHEN** heuristic finds `{name: "Acme", url: "https://acme.com"}` but AI does not
- **THEN** the company is sent to AI validation: "Is Acme at acme.com a portfolio company of {firm}?"
- **AND** included only if AI responds yes

### Requirement: AI validation prompt externalized
The validation prompt SHALL be stored in `src/pipeline/prompts/templates/validate_portfolio_company.md`.

#### Scenario: Validation prompt loaded from file
- **WHEN** a remainder company needs validation
- **THEN** the prompt is loaded from the external template file

### Requirement: URL domain normalization for matching
URL matching SHALL normalize by: stripping `www.` prefix, removing trailing slashes, comparing netloc only (ignore path, query, fragment).

#### Scenario: URLs with www difference match
- **WHEN** comparing `https://www.stripe.com/` and `https://stripe.com`
- **THEN** they are considered the same company (domains match after normalization)

### Requirement: Diagnostic logging
The discovery process SHALL log at INFO level: total links scraped, links rejected per filter (with filter name), candidates from each path, intersection count, remainder count, validation results, and final company count.

#### Scenario: Diagnostic log output
- **WHEN** discovery runs on perotjain.com
- **THEN** logs show: "Scraped 100 links from 6 paths. Heuristic: 18 candidates. AI: 15 candidates. Intersection: 14. Remainder: 5 (3 validated). Final: 17 companies."

### Requirement: Meaningful feedback for 0 results
When 0 companies are discovered, the response SHALL include a diagnostic message explaining why: "No portfolio pages found at expected paths" or "Page found but no portfolio company links detected" or "This appears to be a professional services firm, not a PE firm with portfolio companies."

#### Scenario: Non-PE firm
- **WHEN** discovery runs on bdo.com (accounting firm)
- **THEN** the response includes `{companies: [], message: "This appears to be a professional services firm. Portfolio discovery works best with PE/VC firm websites."}`

#### Scenario: PE firm with unusual structure
- **WHEN** discovery runs but all links are filtered
- **THEN** the response includes `{companies: [], message: "Found links but couldn't identify portfolio companies. The site may use an unusual page structure."}`
