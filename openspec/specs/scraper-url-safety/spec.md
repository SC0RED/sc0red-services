# scraper-url-safety Specification

## Purpose
Guards every server-side URL fetch (the `fetch_page_html` chokepoint) against SSRF — rejecting non-public targets and re-validating each redirect hop — so a customer-supplied URL can't coerce requests to internal/loopback/metadata hosts.
## Requirements
### Requirement: Server-side fetches reject non-public targets

Every server-side page fetch (the single chokepoint `fetch_page_html`) SHALL
validate the target URL before issuing a request and SHALL refuse any URL that
is not a public `http(s)` resource.

#### Scenario: Non-http(s) scheme is rejected
- **WHEN** a fetch is requested for a `file://`, `ftp://`, `gopher://`, or other
  non-`http(s)` URL
- **THEN** the fetch is refused with `UnsafeUrlError` and no network request is made

#### Scenario: Loopback / private / link-local / metadata host is rejected
- **WHEN** the target host resolves to a loopback (`127.0.0.0/8`, `::1`),
  private (`10/8`, `172.16/12`, `192.168/16`, `fc00::/7`), link-local
  (`169.254/16` incl. the `169.254.169.254` cloud-metadata IP, `fe80::/10`),
  multicast, reserved, or unspecified (`0.0.0.0`, `::`) address
- **THEN** the fetch is refused with `UnsafeUrlError` and no network request is made

#### Scenario: Every resolved record is checked
- **WHEN** a host resolves to multiple addresses and any one of them is a blocked
  (non-public) address
- **THEN** the fetch is refused, regardless of the order of the records

#### Scenario: IPv4-mapped IPv6 cannot smuggle a blocked address
- **WHEN** a host resolves to an IPv4-mapped IPv6 address (`::ffff:a.b.c.d`)
  whose embedded IPv4 is blocked
- **THEN** the fetch is refused with `UnsafeUrlError`

#### Scenario: Unresolvable host is rejected
- **WHEN** the target host cannot be resolved
- **THEN** the fetch is refused with `UnsafeUrlError`

#### Scenario: A legitimate public URL is fetched
- **WHEN** the target host resolves only to public addresses
- **THEN** the fetch proceeds normally

### Requirement: Redirects are validated per hop

The scraper SHALL NOT auto-follow redirects into unvalidated targets; it SHALL
follow redirects manually and re-validate each hop.

#### Scenario: Redirect into a blocked range is rejected
- **WHEN** an allowed public URL responds with a 3xx whose `Location` resolves to
  a blocked (private/loopback/link-local/etc.) address
- **THEN** the redirect is not followed and the fetch is refused with `UnsafeUrlError`

#### Scenario: Redirect to another public URL is followed
- **WHEN** an allowed public URL redirects to another public URL
- **THEN** the redirect is followed and the destination body is returned

#### Scenario: Redirect loops are bounded
- **WHEN** the number of redirects exceeds the maximum
- **THEN** the fetch is refused with `UnsafeUrlError`

### Requirement: Test/local stacks may opt out via env

The IP-range checks SHALL be skippable via the `SCRAPER_ALLOW_PRIVATE_HOSTS`
environment variable so the E2E and local docker stacks can scrape an internal
mock host. The opt-out SHALL be off by default (production is guarded with no
extra configuration) and SHALL NOT relax the scheme/host validation.

#### Scenario: Opt-out allows a private host in test
- **WHEN** `SCRAPER_ALLOW_PRIVATE_HOSTS` is truthy and a fetch targets a private
  docker host over http
- **THEN** the IP-range check is skipped and the fetch proceeds

#### Scenario: Opt-out still rejects bad schemes
- **WHEN** `SCRAPER_ALLOW_PRIVATE_HOSTS` is truthy and a fetch targets a
  non-`http(s)` scheme
- **THEN** the fetch is still refused with `UnsafeUrlError`

