## MODIFIED Requirements

### Requirement: Strategy maps are generated on-demand via a dedicated API + worker, not as part of the analysis pipeline

The company analysis pipeline SHALL NOT include a `GenerateStrategyMap` step. Instead, strategy maps are generated on-demand: a user clicks a CTA on the analysis page, the frontend POSTs to `POST /api/analysis/{id}/strategy-map`, the API handler enqueues an SQS message on the dedicated `janus-strategy-map-queue`, the worker Lambda consumes the message and runs the generation against the existing analysis data, and the worker persists the result + pushes a completion event via AppSync.

The on-demand worker SHALL consume the same input shape as the previous pipeline-step did: scraped content + `CompanyProfile` + `RiskAssessment` + `OpportunityResult` + `EbitdaTreeResult` + `ValueChainResult` + uploaded document text + the Vector white-paper system prompt + Mobil/Wawa exemplars. The strategy-map generation algorithm itself is unchanged — only the trigger and timing change.

The strategy map SHALL be persisted on the assessment record (`assessment_repo.save_strategy_map(...)`) and SHALL be returned by `GET /api/analysis/{id}` as a `strategyMap` field on the response when present, omitted when absent.

A `strategy_map_generation_state` field on the COMPANY record (not the assessment record) SHALL track in-flight generation: present with value `"generating"` while the worker is processing, absent otherwise. The frontend reads this on `GET /api/analysis/{id}` to render the appropriate UI state on cold load and on refresh during generation.

#### Scenario: Newly analysed company has no strategy map until generation is requested

- **WHEN** a fresh company analysis completes
- **THEN** the persisted assessment record does NOT contain a `strategyMap` field
- **AND** the API response from `GET /api/analysis/{id}` omits the `strategyMap` field
- **AND** the frontend renders the strategy-map slot in CTA state ("Generate strategy map" button)

#### Scenario: User clicks "Generate strategy map"

- **WHEN** the frontend POSTs to `/api/analysis/{id}/strategy-map`
- **THEN** the handler validates the analysis exists + the user has access (org check), sets `strategy_map_generation_state = "generating"` on the company record, enqueues an SQS message on `janus-strategy-map-queue` carrying `{analysis_id, scan_id}`, and returns 202 Accepted immediately
- **AND** subsequent `GET /api/analysis/{id}` responses surface the `"generating"` state until the worker completes

#### Scenario: Worker completes generation

- **WHEN** the strategy-map worker Lambda finishes generation successfully
- **THEN** the worker persists the strategy map via `assessment_repo.save_strategy_map(...)`, clears `strategy_map_generation_state` from the company record, and pushes an AppSync `strategy_map_complete` event keyed by `analysis_id`
- **AND** subsequent `GET /api/analysis/{id}` responses include the `strategyMap` field
- **AND** the frontend, on receipt of the AppSync event OR via natural cold-load, transitions to the present state and renders `StrategyMapView`

#### Scenario: Worker fails generation

- **WHEN** the strategy-map worker Lambda fails to generate (e.g., AI client error, schema validation failure)
- **THEN** the worker logs the error to CloudWatch, clears `strategy_map_generation_state` from the company record, and pushes an AppSync `strategy_map_failed` event with a generic error message
- **AND** the frontend transitions back to CTA state with a "Generation failed — try again" message above the button
- **AND** the SQS message is retried up to 3 times before landing in the DLQ (CloudWatch alarm fires for ops)

### Requirement: Re-analysing a company invalidates the persisted strategy map

When a re-analyse is triggered on a company (with or without document upload), the re-analyse handler SHALL clear the persisted strategy map from the assessment record before the analysis pipeline starts. The strategy map is invalidated unconditionally on every re-analyse — re-analyse can update scraped content, profile, risks, opportunities, EBITDA, and value chain even without a document upload, all of which feed the strategy-map generation. Tying invalidation only to "with new docs" would surface stale strategy maps relative to a refreshed diagnosis.

The frontend SHALL render the CTA state after re-analyse completes; users explicitly re-generate by clicking "Generate strategy map" against the new diagnosis.

#### Scenario: Re-analyse without document upload clears the map

- **WHEN** a user clicks Re-analyse on an analysis that has a persisted strategy map (no documents uploaded in the same action)
- **THEN** the persisted strategy map is cleared from the assessment record before the pipeline runs
- **AND** the post-re-analyse `GET /api/analysis/{id}` response omits the `strategyMap` field
- **AND** the frontend renders the strategy-map slot in CTA state

#### Scenario: Re-analyse with document upload also clears the map

- **WHEN** a user uploads a new document and clicks Re-analyse
- **THEN** the persisted strategy map is cleared from the assessment record before the pipeline runs (same as the no-document case)

### Requirement: Existing strategy maps remain visible until invalidated

Strategy maps generated by the legacy pipeline-step path (before this change) SHALL continue to render on the analysis page after this change ships. They are not retroactively cleared. They are invalidated only when a re-analyse fires (per the re-analyse-invalidation requirement).

#### Scenario: Pre-change analysis still shows its auto-generated map

- **WHEN** an analysis whose strategy map was auto-generated before this change is loaded
- **THEN** `GET /api/analysis/{id}` returns the strategy map as before
- **AND** the frontend renders `StrategyMapView` in the present state at Beat 6

## ADDED Requirements

### Requirement: Strategy-map generation pushes completion events via AppSync

The strategy-map worker Lambda SHALL push completion events via the existing AppSync infrastructure on the same event channel used for pipeline progress (`appsync_notifier`). Two event types:

- `strategy_map_complete` payload: `{analysis_id, scan_id}`. Fired on successful generation.
- `strategy_map_failed` payload: `{analysis_id, scan_id, error_message}`. Fired on worker error after retries.

The events do NOT carry the strategy-map content — frontend re-fetches via `GET /api/analysis/{id}` on receipt of `strategy_map_complete`. This keeps the persistence layer (DynamoDB) as the single source of truth and keeps AppSync payloads small.

The frontend hook `useStrategyMapSubscription(analysisId)` SHALL filter AppSync events on `analysis_id` and trigger a re-fetch on `complete` or transition to failure UI on `failed`. The hook SHALL implement a 90-second client-side timeout that triggers a one-time fallback `GET /api/analysis/{id}` if no AppSync event arrives — guarding against dropped subscriptions.

#### Scenario: Frontend renders the result via AppSync push

- **WHEN** the frontend is in generating state, subscribed to AppSync, and the worker pushes `strategy_map_complete`
- **THEN** the hook triggers a `GET /api/analysis/{id}` fetch
- **AND** the response carries the persisted strategy map
- **AND** the slot transitions to the present state without a manual refresh

#### Scenario: AppSync push is dropped; client-side fallback fires

- **WHEN** the frontend is in generating state for 90+ seconds without an AppSync event
- **THEN** the subscription hook fires a one-time fallback `GET /api/analysis/{id}`
- **AND** if the response carries the map (worker completed, AppSync dropped), the slot transitions to present
- **AND** if the response still shows generating state, the slot continues to wait for AppSync without further fallbacks

### Requirement: Strategy-map generation has its own dedicated SQS queue + worker Lambda

The infrastructure SHALL provide a dedicated `janus-strategy-map-queue` SQS queue + DLQ + CloudWatch alarm on DLQ depth (per environment), defined in `infrastructure/stacks/janus_stack.py`. The queue is consumed by a dedicated `strategy_map_handler` Lambda whose only job is to run strategy-map generation jobs.

The queue is dedicated (not piggy-backed on the existing `janus-analysis-queue`) for three reasons documented in `design.md` Decision §2: independent scaling, independent monitoring, isolated failure blast radius.

#### Scenario: Worker drains the dedicated queue

- **WHEN** an SQS message lands on `janus-strategy-map-queue`
- **THEN** only the `strategy_map_handler` Lambda processes it
- **AND** the analysis-pipeline worker Lambda is unaffected (no shared visibility timeout, no shared concurrency budget)

#### Scenario: DLQ depth alarm fires on persistent failures

- **WHEN** strategy-map generation fails 3 times for the same SQS message and lands in the DLQ
- **THEN** the CloudWatch alarm on DLQ depth fires for ops
- **AND** the front-end already showed the user a "Generation failed — try again" message via the AppSync `strategy_map_failed` event

## REMOVED Requirements

### Requirement: Analysis pipeline generates a Balanced Scorecard strategy map

**Reason**: replaced by the on-demand-generation requirement above. The pipeline no longer auto-generates a strategy map for every analysed company.

**Migration**: existing analyses' persisted strategy maps remain visible. New analyses start with the strategy-map slot in CTA state; users opt in by clicking "Generate strategy map." Re-analysing any analysis (existing or new) clears the persisted map and returns the slot to CTA state.
