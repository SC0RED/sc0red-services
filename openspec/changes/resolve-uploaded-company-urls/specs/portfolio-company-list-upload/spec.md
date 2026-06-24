# Spec — portfolio-company-list-upload (URL resolution)

## ADDED Requirements

### Requirement: Name-only uploaded companies can be resolved to a URL

When an uploaded/added company has a name but no `http(s)` URL, the system SHALL
offer to resolve it to the company's official website URL (via a grounded
lookup), so a name-only list can be analyzed. Resolved URLs SHALL enter the
needs-validation tier (candidates to confirm, not asserted), and low-confidence
or ambiguous resolutions SHALL be surfaced for customer confirmation rather than
auto-accepted.

#### Scenario: Name-only upload becomes analyzable
- **WHEN** a customer uploads a list of company names without URLs and requests resolution
- **THEN** each name is resolved to a candidate official URL and presented for
  review, after which the companies can be selected and analyzed

#### Scenario: Ambiguous name is confirmed, not guessed
- **WHEN** a name resolves with low confidence or to multiple plausible companies
- **THEN** the customer is asked to confirm/choose rather than the system silently
  picking one

#### Scenario: Unresolved names are not silently dropped
- **WHEN** a name cannot be resolved to a URL
- **THEN** it remains visible and excluded-with-explanation (the honest-fix
  behaviour), never silently discarded at confirm
