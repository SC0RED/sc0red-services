## ADDED Requirements

### Requirement: Analyses list paginates via cursor

The `/analyses` page SHALL fetch results in pages of size 50 (default; configurable via `?limit=`). The backend response includes a `cursor` field when more results exist; the frontend uses this cursor to load subsequent pages. The frontend SHALL NOT fetch all results upfront.

#### Scenario: Initial load fetches first page only

- **WHEN** the user navigates to `/analyses`
- **THEN** the frontend fetches `GET /api/analyses?limit=50` and renders the returned analyses; the response cursor (if present) is held in component state

#### Scenario: User loads next page

- **WHEN** the user clicks "Load More" (or paginates) and a cursor is present
- **THEN** the frontend fetches `GET /api/analyses?limit=50&cursor={cursor}` and appends the results to the current list

#### Scenario: Last page hides Load More

- **WHEN** the response from `/api/analyses` returns no `cursor` field (last page)
- **THEN** the "Load More" affordance is hidden

### Requirement: Analyses search runs server-side

The `/analyses` page SHALL pass user-typed search input as a `q` query parameter to the backend. The backend SHALL perform fuzzy search over `company_name` and `industry`. Search input SHALL be debounced 300ms before firing the request.

#### Scenario: User types a search query

- **WHEN** the user types "acm" in the search field
- **THEN** after 300ms of no further keypresses, the frontend fetches `GET /api/analyses?q=acm&limit=50` and renders the matched analyses

#### Scenario: Empty search returns all analyses

- **WHEN** the user clears the search field
- **THEN** the frontend fetches `GET /api/analyses?limit=50` (no `q` param) and renders the unfiltered first page

#### Scenario: Search resets pagination

- **WHEN** the user is on page 3 and types a new search query
- **THEN** the frontend fetches the new search starting from no cursor (first page); the previously-loaded results are replaced

### Requirement: Filter and sort state lives in the URL

The `/analyses` page SHALL read and write its filter and sort state via URL query parameters (`q`, `tier`, `type`, `sort`). State SHALL NOT be stored in component-only state. The URL SHALL be the single source of truth for the current view.

#### Scenario: User filters and shares the URL

- **WHEN** the user filters to `tier=high&type=portfolio` and copies the URL
- **THEN** the URL contains `?tier=high&type=portfolio` (in addition to any active search/sort), and a recipient opening the URL sees the same filtered view

#### Scenario: Page refresh preserves filters

- **WHEN** the user has filters applied and refreshes the page
- **THEN** the filters remain applied (read from the URL on mount)

#### Scenario: Default state has no query params

- **WHEN** the user is on `/analyses` with no filters/search/sort applied
- **THEN** the URL is exactly `/analyses` with no query string

### Requirement: Filter and sort act on the loaded slice

Tier and type filters, plus sort order, SHALL be applied client-side over the currently-loaded analyses (the union of all pages fetched so far). They SHALL NOT trigger new backend requests.

#### Scenario: Filter narrows loaded results

- **WHEN**50 analyses are loaded and the user clicks "tier=high"
- **THEN** the table renders only the high-tier subset of the 50 loaded; no API call is made

#### Scenario: Sort reorders loaded results

- **WHEN** the user clicks the "Risk Score" column header
- **THEN** the loaded analyses re-render sorted by score desc; no API call is made
