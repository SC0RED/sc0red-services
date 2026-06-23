## ADDED Requirements

### Requirement: Scraper fetches via a browser-impersonating TLS transport

The web scraper's HTTP fetch (`scrape_url`) SHALL use a transport that presents a real-browser TLS/HTTP-2 fingerprint (`curl_cffi` with browser impersonation) as its sole transport, so that fingerprint-based bot protection (e.g. Cloudflare JA3 bot management) returns full page content rather than a `403`/challenge response. The transport SHALL impersonate a current browser target and follow redirects; on the impersonated path it SHALL rely on the transport's browser-consistent header set rather than hand-rolled scraper headers.

#### Scenario: TLS-fingerprint-gated site returns full content

- **WHEN** `scrape_url` is called for a site behind TLS-fingerprint bot protection that returns `403` to a non-browser client
- **THEN** the request is made with a browser-impersonating fingerprint
- **AND** the site returns `200` with its full HTML, which is parsed into title/text/links as for any other site

#### Scenario: Ordinary site is unaffected

- **WHEN** `scrape_url` is called for a site with no bot protection
- **THEN** the page is fetched and parsed identically to before, including the embedded-`<script>`-JSON extraction path

#### Scenario: Redirects are followed

- **WHEN** the fetched URL responds with a redirect to a final location
- **THEN** the transport follows the redirect and parses the final response

### Requirement: Scrape failures surface the underlying cause

When a scrape returns too little usable content, the error raised SHALL include the underlying transport failure (the HTTP status code or transport error) when one is known, rather than reporting only a generic "insufficient content" message — so that a bot block or a dead site is diagnosable from the error alone.

#### Scenario: Bot block surfaces the HTTP status

- **WHEN** a scrape yields no usable content because the transport received an HTTP error status (e.g. `403`)
- **THEN** the raised error message includes that status (e.g. references `HTTP 403`)
- **AND** does not report a bare "insufficient content" message that hides the status

#### Scenario: Genuinely thin page still reported as insufficient content

- **WHEN** a scrape succeeds (`200`) but the page genuinely has fewer than the minimum required characters of content
- **THEN** the raised error reports insufficient content (no HTTP error status is implied)

### Requirement: Transport errors fail fast without masking bugs

The scraper SHALL catch only expected transport/domain errors from the impersonating transport (bad HTTP status, connection, and timeout errors). Programming errors (e.g. `AttributeError`, `KeyError`, `TypeError`) SHALL propagate rather than being converted into an empty-content result.

#### Scenario: Transport error degrades to empty result

- **WHEN** the transport raises a connection or timeout error for a URL
- **THEN** the scraper returns the same empty-content/error contract that callers already handle, without raising

#### Scenario: Programming error propagates

- **WHEN** a programming error occurs inside the scrape path
- **THEN** it propagates to the caller (and to the worker retry / logs) rather than being swallowed as an empty scrape
