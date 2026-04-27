## ADDED Requirements

### Requirement: CTA banner emits expand and collapse events on the web

The web `Sc0redCTABanner` component SHALL emit a `sc0red_cta_banner_expanded` event when the user opens the banner and a `sc0red_cta_banner_collapsed` event when the user closes it again. Events SHALL include `analysis_id`, `opportunity_count`, and `active_lever_filter` in the payload.

#### Scenario: User expands the collapsed banner

- **WHEN** the banner is collapsed and the user clicks the toggle
- **THEN** an event with `event_type = "sc0red_cta_banner_expanded"` is posted to `POST /analytics/events`, and the banner visually expands

#### Scenario: User collapses the expanded banner

- **WHEN** the banner is expanded and the user clicks the toggle
- **THEN** an event with `event_type = "sc0red_cta_banner_collapsed"` is posted to `POST /analytics/events`, and the banner visually collapses

#### Scenario: Emit failure does not block the UI

- **WHEN** the analytics endpoint returns a non-2xx status or the network request fails
- **THEN** the banner's expand/collapse visual state updates normally, no user-visible error surfaces, and a console warning is logged in development builds only

### Requirement: CTA link click emits a click event before navigation

The web `Sc0redCTABanner` SHALL emit `sc0red_cta_clicked` when the user activates the "Start the conversation" link. The event SHALL be sent before the new tab navigates. Because the link uses `target="_blank"`, awaiting the emit does not delay the user's navigation.

#### Scenario: User clicks the CTA link

- **WHEN** the user clicks "Start the conversation"
- **THEN** a `sc0red_cta_clicked` event is posted, AND a new tab opens to the sc0red contact URL. If the emit succeeds, the event reaches the backend. If it fails, the navigation still occurs.

#### Scenario: Emit resolves before navigation on fast networks

- **WHEN** the emit completes within a typical round trip (< 500ms)
- **THEN** the event is recorded in CloudWatch before the destination tab finishes loading

### Requirement: PDF export emits a render event

The Next.js PDF export route SHALL emit `sc0red_cta_rendered_in_pdf` after successfully generating a PDF that contains the CTA block. The event SHALL carry `source: "pdf"` and `analysis_id`.

#### Scenario: A user exports a PDF that includes opportunities

- **WHEN** `GET /api/export/pdf/{analysisId}` returns the PDF response
- **THEN** before returning the response, a `sc0red_cta_rendered_in_pdf` event is posted with `analysis_id` and `source: "pdf"`

#### Scenario: PDF emit failure does not block the download

- **WHEN** the analytics emit fails
- **THEN** the PDF response is still returned to the user, and the failure is logged on the server side

### Requirement: Backend analytics endpoint validates and enriches events

The backend SHALL expose `POST /analytics/events` that accepts a validated event envelope, enriches it with `user_id` and `org_id` from the authenticated JWT, and writes the result as a structured JSON log entry to the dedicated analytics log group. The backend SHALL ignore any `user_id` or `org_id` fields present in the request body.

#### Scenario: Authenticated client posts a well-formed event

- **WHEN** a client sends `POST /analytics/events` with `{event_id, event_type, timestamp, analytics_version, source, analysis_id, opportunity_count, active_lever_filter}` and a valid Cognito `Authorization` header
- **THEN** the backend responds `202 Accepted`, writes a JSON log line to the `/janus/{env}/analytics-events` log group containing all envelope fields PLUS `user_id` and `org_id` pulled from the JWT

#### Scenario: Client attempts to spoof org_id

- **WHEN** the request body includes `org_id: "other-org"` but the JWT belongs to `org_id: "real-org"`
- **THEN** the logged event records `org_id: "real-org"` (the JWT value); the body's `org_id` is ignored

#### Scenario: Malformed envelope is rejected

- **WHEN** the request body is missing `event_type` or sends an unknown `event_type`
- **THEN** the backend responds `400 Bad Request` with a validation error, and no log entry is written

#### Scenario: Unauthenticated request is rejected

- **WHEN** the request has no `Authorization` header or an expired token
- **THEN** the backend responds `401 Unauthorized`, and no log entry is written

### Requirement: Analytics events are queryable via CloudWatch Logs Insights

The dedicated analytics log group SHALL retain events for 90 days and SHALL be queryable via Logs Insights using field projections on `event_type`, `org_id`, `analysis_id`, `user_id`, `timestamp`, `source`, and `opportunity_count`.

#### Scenario: Funnel query returns counts by event type

- **WHEN** an operator runs `stats count() by event_type` over the last 7 days in Logs Insights
- **THEN** the query returns one row per event type present in the window, with accurate counts matching the emitted events

#### Scenario: Per-org breakdown query

- **WHEN** an operator runs a Logs Insights query that filters by `event_type = 'sc0red_cta_clicked'` and groups by `org_id`
- **THEN** the query returns one row per org that clicked, with click counts
