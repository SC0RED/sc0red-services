## ADDED Requirements

### Requirement: Customer can supply a reliable source URL to fetch from

From the confirmation screen, the customer SHALL be able to provide the URL of a page that lists the firm's portfolio (e.g. the firm's `/investments` page we missed, or a source they trust). The system SHALL fetch that URL server-side and run the same trusted extraction used for the firm's own site, producing high-confidence `provided_url` candidates that merge into the existing set (trusted-source-wins dedup). This is offered alongside CSV/PDF upload as a second reliable correction path, and is distinct from the lower-confidence "search deeper" web search.

#### Scenario: Customer points us at the right page

- **WHEN** the customer pastes the URL of a page that lists the portfolio and submits it
- **THEN** the system fetches that page server-side, extracts companies as `provided_url` (high-confidence), merges them into the candidate set (deduped, trusted-wins), and returns an updated verdict

#### Scenario: Provided page is itself client-side-rendered

- **WHEN** the provided URL is a page that builds its list dynamically in the browser
- **THEN** extraction may still come up short, and the customer is told the page loaded dynamically and is pointed to CSV/PDF upload — the attempt does not fail silently

### Requirement: Provided-URL fetching is server-side and bounded

Fetching a customer-provided URL SHALL use the existing server-side scraper (no browser, so no cross-origin restriction) and SHALL be subject to the same fetch resilience and limits as firm-site scraping (timeouts, retry, size caps). A fetch failure SHALL surface a clear message and leave the existing candidate list intact, not fail the scan.

#### Scenario: Provided URL can't be reached

- **WHEN** the provided URL fails to fetch after retries
- **THEN** the customer is told it couldn't be reached, the existing candidates are unchanged, and upload remains offered
