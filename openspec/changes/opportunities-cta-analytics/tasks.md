## 1. Backend — models and envelope validation

- [ ] 1.1 Create `backend/src/models/analytics_events.py` with a Pydantic discriminated union keyed on `event_type`
- [ ] 1.2 Define envelope fields: `event_id`, `event_type`, `timestamp`, `analytics_version`, `source`, `analysis_id`, `opportunity_count`, `active_lever_filter`
- [ ] 1.3 Add a `EnrichedAnalyticsEvent` model that composes the envelope with server-enriched `user_id` + `org_id`
- [ ] 1.4 Enumerate allowed `event_type` values: `sc0red_cta_banner_expanded`, `sc0red_cta_banner_collapsed`, `sc0red_cta_clicked`, `sc0red_cta_rendered_in_pdf`
- [ ] 1.5 Unit tests in `backend/tests/unit/models/test_analytics_events.py` — each event type, invalid envelope rejections, unknown event_type rejection

## 2. Backend — analytics logger utility

- [ ] 2.1 Create `backend/src/utilities/analytics_logger.py` with `log_event(enriched_event: EnrichedAnalyticsEvent) -> None`
- [ ] 2.2 Reads `ANALYTICS_LOG_GROUP` env var; uses boto3 CloudWatch Logs `put_log_events` with a consistent log stream name per Lambda execution context (`{lambda_request_id}` or similar)
- [ ] 2.3 Fails loudly if `ANALYTICS_LOG_GROUP` is unset in non-development environments (fail-fast pattern)
- [ ] 2.4 Unit tests: successful write, missing env var behaviour, CloudWatch API error propagation

## 3. Backend — handler + routing

- [ ] 3.1 Create `backend/src/handlers/analytics_handlers.py` with `handle_post_event(event: dict, auth_context) -> dict`
- [ ] 3.2 Validate body via Pydantic; return 400 on validation error
- [ ] 3.3 Enrich with `user_id` + `org_id` from `auth_context` (ignore any values in body)
- [ ] 3.4 Call `analytics_logger.log_event(...)`; return `{"statusCode": 202}` on success
- [ ] 3.5 Register `POST /analytics/events` in `backend/src/handlers/api_gateway_handler.py` dispatch table
- [ ] 3.6 Unit tests in `backend/tests/unit/handlers/test_analytics_handlers.py`: happy path (202), spoof rejection (org_id from JWT wins), malformed (400), unauthenticated (401)

## 4. Infrastructure — CloudWatch log group + IAM

- [ ] 4.1 Add `logs.LogGroup` to `janus_stack.py`: name `/janus/{environment}/analytics-events`, retention 90 days
- [ ] 4.2 Grant the API Lambda `logs:PutLogEvents` on the log group (and `logs:CreateLogStream`)
- [ ] 4.3 Export log group name as `ANALYTICS_LOG_GROUP` env var on the API Lambda
- [ ] 4.4 Verify `cdk synth` succeeds locally
- [ ] 4.5 Update `scripts/setup_dynamodb.py` / LocalStack setup if needed (probably not — LocalStack supports CloudWatch Logs natively)

## 5. Frontend — typed emit helpers

- [ ] 5.1 Create `frontend/src/lib/analytics/emitEvent.ts` with `emit(eventType, context)` returning a Promise; generates `event_id` + `timestamp` client-side
- [ ] 5.2 Create `frontend/src/lib/analytics/emitEvent.server.ts` exporting `emitFromServer(eventType, context, authContext)` — uses `backendFetch()`
- [ ] 5.3 Shared TypeScript types in `frontend/src/lib/types/analytics.ts` — mirrors the Pydantic envelope
- [ ] 5.4 Vitest tests in `frontend/src/tests/lib/analytics/emitEvent.test.ts`: successful post, network failure is swallowed (no throw), correct endpoint + body shape

## 6. Frontend — Next.js proxy route

- [ ] 6.1 Create `frontend/src/app/api/analytics/events/route.ts` — POST handler, pulls NextAuth token, calls `backendFetch('/analytics/events', ...)`
- [ ] 6.2 Return 401 if no session; 202 on success; proxy any 4xx/5xx status from backend
- [ ] 6.3 Unit tests for the route: authenticated request forwards correctly, unauthenticated returns 401

## 7. Frontend — CTA banner wiring

- [ ] 7.1 Add `analysisId` + `opportunityCount` + `activeLeverFilter` props to `Sc0redCTABanner` component signature
- [ ] 7.2 Emit `sc0red_cta_banner_expanded` / `sc0red_cta_banner_collapsed` inside the toggle handler (fire-and-forget)
- [ ] 7.3 Emit `sc0red_cta_clicked` on the link click handler with `await` before default navigation; link retains `target="_blank"`
- [ ] 7.4 Update `OpportunitiesList` to pass the new props through: `analysisId={analysisId} opportunityCount={filteredOpps.length} activeLeverFilter={activeLeverFilter}`
- [ ] 7.5 Update `frontend/src/tests/components/Sc0redCTABanner.test.tsx`: mock `emit`, assert it is called with the correct event type + payload on each interaction
- [ ] 7.6 Verify existing `OpportunitiesList.test.tsx` still passes (pass-through prop change only)

## 8. Frontend — PDF render emission

- [ ] 8.1 In `frontend/src/app/api/export/pdf/[analysisId]/route.ts`, after a successful PDF render, call `emitFromServer('sc0red_cta_rendered_in_pdf', {analysis_id, opportunity_count, source: 'pdf'})` before returning the response
- [ ] 8.2 If the emit fails, log server-side and continue — the PDF download must succeed
- [ ] 8.3 Add a test that mocks `emitFromServer` and asserts it is called on successful PDF generation

## 9. Quality gates

- [ ] 9.1 Backend: `uv run ruff check src/` — zero errors
- [ ] 9.2 Backend: `uv run pyright src/` — no new errors vs baseline
- [ ] 9.3 Backend: `uv run pytest tests/ -q` — all pass, coverage ≥ 95%
- [ ] 9.4 Frontend: `npm run lint && npx tsc --noEmit && npm test` — lint clean, typecheck clean, all tests pass
- [ ] 9.5 CDK synth passes locally
- [ ] 9.6 `architecture-reviewer` agent — no CRITICAL findings; MEDIUM findings addressed or deferred with user approval
- [ ] 9.7 E2E: run `scripts/e2e-test.sh` in `E2E_MODE=full` — no regressions

## 10. Deploy + verify

- [ ] 10.1 Open PR against `development`; CI green
- [ ] 10.2 Deploy to `development` AWS account
- [ ] 10.3 Manually: expand the banner on any analysis; confirm a Logs Insights query for the last 5 minutes shows the event
- [ ] 10.4 Manually: click the CTA link; confirm `sc0red_cta_clicked` appears in the log group
- [ ] 10.5 Manually: export a PDF; confirm `sc0red_cta_rendered_in_pdf` appears in the log group with `source: "pdf"`
- [ ] 10.6 Run the four sample Logs Insights queries from `design.md` in the dev account; verify syntax and shape
- [ ] 10.7 Promote `development` → `testing` → `production`
- [ ] 10.8 Run the same funnel queries against the `production` log group 72 hours post-deploy; establish the baseline click-through rate and record it in this change's retrospective

## 11. Follow-up / documentation

- [ ] 11.1 Add a `docs/analytics/queries.md` page with the four sample queries + instructions for running them in Logs Insights
- [ ] 11.2 Decide (post-baseline) whether `sc0red_cta_banner_collapsed` is useful or should be dropped — recorded as a note in the spec's open questions
