## ADDED Requirements

### Requirement: Scrape transport retries transient failures

The scraping transport SHALL retry a fetch that fails with a transient or bot-challenge response — HTTP 403, 408, 425, 429, or 5xx, or a connection/timeout error — a bounded number of times with a brief backoff before raising. Genuine non-retryable responses (e.g. 404, 410) SHALL NOT be retried. A misconfigured impersonation target (programming error) SHALL propagate immediately, not be retried.

#### Scenario: Transient block succeeds on retry

- **WHEN** the first fetch of a page returns HTTP 403 (a Cloudflare challenge) and a subsequent attempt returns 200
- **THEN** the transport returns the 200 content (the retry is transparent to callers)

#### Scenario: Not-found is not retried

- **WHEN** a fetch returns HTTP 404
- **THEN** the transport raises immediately without retrying

#### Scenario: Persistent failure raises after exhausting retries

- **WHEN** every attempt fails with a retryable error
- **THEN** the transport raises the last error after the bounded number of attempts

### Requirement: Web-search fallback distinguishes genuine-zero from fetch failure

Portfolio discovery SHALL track whether a portfolio listing page fetch failed (a non-404 error persisting after retries) versus genuinely returned content with no companies. When the web-search fallback fires, the discovery step SHALL log the cause — fetch failure versus genuine empty site — at WARNING for a fetch failure, so an intermittent block that degrades the result to the web-search subset is observable rather than silent. The fallback remains the recovery path in both cases.

#### Scenario: Fallback after a fetch failure is logged as such

- **WHEN** the listing page fetch fails after retries and the web-search fallback then runs
- **THEN** a WARNING is logged indicating the fallback fired because the site fetch failed (results may be incomplete)

#### Scenario: Fallback on a genuinely empty site

- **WHEN** the site is fetched successfully but yields no companies (e.g. an opaque client-side-rendered firm)
- **THEN** the fallback fires as the normal recovery without a fetch-failure warning
