## MODIFIED Requirements

### Requirement: Confidence-based result merging
Discovery results from the heuristic and AI paths SHALL be merged using normalized-URL matching (netloc + path). Companies found by both paths (intersection) SHALL be auto-included. Companies found by only one path (remainder) SHALL be validated by AI. Candidates that share a domain but have distinct paths (e.g. a firm's per-company detail pages) SHALL be treated as distinct companies, not collapsed.

#### Scenario: Company in both paths
- **WHEN** heuristic finds `{name: "Stripe", url: "https://stripe.com"}` and AI finds `{name: "Stripe Inc", url: "https://www.stripe.com"}`
- **THEN** the company is auto-included (normalized URLs match: same netloc, root path)

#### Scenario: Company in one path only
- **WHEN** heuristic finds `{name: "Acme", url: "https://acme.com"}` but AI does not
- **THEN** the company is sent to AI validation: "Is Acme at acme.com a portfolio company of {firm}?"
- **AND** included only if AI responds yes

#### Scenario: Distinct same-domain detail pages are not collapsed
- **WHEN** discovery yields many candidates on one domain with distinct paths (e.g. `https://firm.com/portfolio/calabrio` and `https://firm.com/portfolio/zipari`)
- **THEN** each is kept as a distinct company through the merge (not deduplicated to one)

### Requirement: URL normalization for matching
URL matching SHALL normalize by: stripping `www.` prefix, lowercasing the host, removing trailing slashes, ignoring query and fragment, and comparing netloc **and** path (so two URLs match only when both host and path are equal after normalization).

#### Scenario: URLs with www difference match
- **WHEN** comparing `https://www.stripe.com/` and `https://stripe.com`
- **THEN** they are considered the same company (host matches after normalization; both have root path)

#### Scenario: Same host, different path do not match
- **WHEN** comparing `https://firm.com/portfolio/a` and `https://firm.com/portfolio/b`
- **THEN** they are considered different companies (paths differ)
