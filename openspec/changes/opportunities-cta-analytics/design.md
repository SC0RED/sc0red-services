## Context

The sc0red CTA banner ships on every opportunity detail view. Two surfaces:

- **Web** — `<Sc0redCTABanner />` renders at the bottom of `OpportunitiesList` when there are opportunities to show. Collapsed by default, one toggle to expand, one external `target="_blank"` link to `getSc0redContactUrl()`.
- **PDF** — server-side render in `frontend/src/app/api/export/pdf/[analysisId]/route.ts`. Same copy, same external link, static HTML → PDF.

Neither surface has any instrumentation. The product question — "is the CTA driving conversations?" — is currently unanswerable.

```
CURRENT:

  Opportunity view ──► <Sc0redCTABanner> (collapsed)
                           │
                           │ user clicks toggle ──► state flip (silent)
                           │ user clicks link ─────► new tab to sc0red.com (silent)
                           ▼
                         ──────
                        (no signal)

  PDF export ─────► HTML with .sc0red-cta block (silent)
                           │
                           ▼
                         ──────
                        (no signal)
```

## Proposed architecture

```
┌──────────────────────────────────────┐
│ Sc0redCTABanner  (frontend, React)   │
│                                      │
│  onExpand/onCollapse → emit(         │
│     'sc0red_cta_banner_expanded',    │
│     { analysis_id, opp_count, ... }  │
│  )                                   │
│                                      │
│  onClick (link)     → await emit(    │
│     'sc0red_cta_clicked', {...}      │
│  ) then let default navigation run   │
└───────────┬──────────────────────────┘
            │ fetch('/api/analytics/events', {POST, body})
            ▼
┌─────────────────────────────────────┐
│ Next.js route                        │
│ /api/analytics/events (route.ts)     │
│                                      │
│  - read NextAuth session             │
│  - call backendFetch('/analytics/    │
│    events', { body, token })         │
└───────────┬─────────────────────────┘
            │ POST /analytics/events   (Authorization: Bearer <cognito id token>)
            ▼
┌────────────────────────────────────────┐
│ API Gateway → Lambda (existing)        │
│                                        │
│   api_gateway_handler.py               │
│     dispatch → analytics_handlers.py   │
│       validate envelope (Pydantic)     │
│       enrich org_id from JWT claims    │
│       logger.info(json.dumps(event))   │
└───────────┬────────────────────────────┘
            │ structured JSON log line
            ▼
┌──────────────────────────────────────┐
│ CloudWatch Log Group                 │
│ /janus/{env}/analytics-events        │
│ retention: 90 days                   │
└────────┬─────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ CloudWatch Logs Insights (ad-hoc)    │
│                                      │
│ fields @timestamp, event_type,       │
│   org_id, analysis_id                │
│ | filter @timestamp > ago(7d)        │
│ | stats count() by event_type        │
└──────────────────────────────────────┘

      (PDF side — server-side render)

┌──────────────────────────────────────┐
│ /api/export/pdf/[analysisId]/route.ts│
│   after renderHtml(), before return: │
│     emit_server('sc0red_cta_rendered │
│       _in_pdf', {analysis_id, ...})  │
└───────────┬──────────────────────────┘
            │ same backendFetch call
            ▼
   (same CloudWatch log group)
```

## Goals / Non-Goals

**Goals:**
- Measurable funnel: rendered → expanded → clicked
- Zero new vendor, zero new secret to rotate
- Same observability stack as the rest of the platform (CloudWatch)
- Server-side enrichment prevents spoofed `org_id`
- Privacy-safe by default: no opportunity content, no IP, no mouse tracking

**Non-Goals:**
- Real-time dashboards (Logs Insights is fine at current volume)
- A/B copy variants (separate future proposal once baseline exists)
- Cross-page analytics (this change is only the CTA surface)
- Per-opportunity engagement signals (hover, scroll depth)
- Batching / `navigator.sendBeacon` (volume is too low to justify)

## Decisions

### Decision 1: Sink = CloudWatch Logs + Insights, not DynamoDB or a SaaS vendor

**Decision**: write each event as a structured JSON line to a dedicated CloudWatch Log Group. Query via Logs Insights.

**Why**:
- **DynamoDB is the wrong tool**: all four GSIs are already allocated (GSI1 org→company/user, GSI2 org→scan, GSI3 company→assessment, GSI4 email→user/invite). Adding a fifth to support analytics queries is CDK churn we don't need, and analytics events pollute operational queries against the main table.
- **SaaS vendors are premature**: PostHog/Amplitude/Segment at our scale (handful of design-partner orgs, hundreds of events per day) add vendor risk, a secret to rotate, browser SDK weight, and a privacy review — without proportional value. At 10× current scale we can revisit.
- **CloudWatch is already wired**: the API Lambda already writes there. Adding a second log group is one CDK line plus a log-group-scoped IAM permission. Logs Insights provides funnel math natively (`stats count() by event_type`).

**Migration path if we outgrow Insights**: CloudWatch subscription filter → Firehose → S3 → Athena, or direct log-group integration with Amplitude's CloudWatch connector. Neither requires code changes to the emitting surfaces — only a subscription rule on the log group.

### Decision 2: Dedicated log group, not the API Lambda's default

**Decision**: create `/janus/{env}/analytics-events` as a separate CloudWatch Log Group, distinct from the existing `/aws/lambda/janus-api-{env}`.

**Why**:
- **Retention**: Lambda logs may have shorter retention for cost reasons (or none set). Analytics events need a predictable 90-day window for funnel analysis over time.
- **Cleaner Insights queries**: Lambda log groups contain cold starts, exception stack traces, pipeline progress events. Filtering to only analytics events wastes scan time and tokens. A dedicated group is self-describing.
- **Future subscription**: if we later pipe to Firehose/Athena, we subscribe only the analytics group, not every log line the API Lambda emits.

### Decision 3: Backend enriches `org_id` from JWT, frontend does not send it

**Decision**: the request body from the frontend contains `event_type`, `analysis_id`, `opportunity_count`, `active_lever_filter`, `source`, `analytics_version`. The backend reads `org_id` and `user_id` from the authenticated Cognito token. The backend ignores any `org_id` or `user_id` sent in the body.

**Why**:
- **Anti-spoofing**: a malicious or confused client cannot attribute their events to another org.
- **Single source of truth**: org membership is in Cognito claims; the frontend should not need to know its own org to emit events.
- **Consistent with existing handlers**: `_get_auth_context()` in the handler modules already pulls org/user from the JWT.

### Decision 4: `sc0red_cta_clicked` fires before navigation, but doesn't block it

**Decision**: the click handler on the link `awaits` `emit()` before allowing default navigation. Because the link opens in a new tab (`target="_blank"`), the current page does not unload, so the `await` is safe — it does not lose the event.

**Why**:
- **Accurate click counts**: we capture the intent even if the target page fails to load.
- **No `sendBeacon` complexity**: beacon / background fetch patterns are only needed when unload cancels in-flight requests. `target="_blank"` sidesteps that.
- **Still fast**: the emit call is non-blocking UX — the link opens immediately for the user because `await` runs in parallel with the browser's click-to-new-tab path.

**Alternative considered**: fire-and-forget without `await`. Rejected — occasional lost events on slow networks, harder to debug.

### Decision 5: PDF emission happens in the Next.js route handler, not the backend

**Decision**: the PDF export route (`frontend/src/app/api/export/pdf/[analysisId]/route.ts`) calls `emit_server('sc0red_cta_rendered_in_pdf', {...})` after successful HTML generation. Uses the same `backendFetch()` mechanism as other SSR calls.

**Why**:
- **Co-located with the render**: the decision to include the CTA in the PDF is made in this file. The emit logic lives beside the decision it's measuring.
- **Same auth path**: the route already has a NextAuth session and a Cognito token. No new auth wiring.
- **No duplicate envelope logic**: the helper used by the web surfaces is reused here.

### Decision 6: Event envelope is versioned

**Decision**: every event carries `analytics_version: "1"`. When the shape evolves (new fields added, renames, retirements), bump the version and keep backward-compatible parsing on the backend for one release cycle.

**Why**:
- Logs Insights queries are written against specific field names; a version field lets us evolve the schema without breaking existing queries.
- Costs nothing today (one extra field per event).

### Decision 7: No per-event endpoint for each event type

**Decision**: a single `POST /analytics/events` accepts any event type via a discriminated union on `event_type`. Pydantic dispatches to the correct validator based on the type.

**Why**:
- **One route, one handler, one test module** — less surface area.
- **Adding event types later is a one-line enum extension**, not a new route + new handler + new test file.
- **Consistent with how the existing `api_gateway_handler.py` routes** — thin dispatch to a handler module that owns all event shapes.

## Event envelope (schema)

```jsonc
{
  // Common envelope (all events)
  "event_id": "uuid-v4",                    // generated client-side
  "event_type": "sc0red_cta_banner_expanded", // enum
  "timestamp": "2026-04-24T12:34:56.789Z",  // ISO 8601, client-side
  "analytics_version": "1",
  "source": "web",                          // "web" | "pdf"

  // Auth context (enriched by backend, IGNORED from request body)
  "user_id": "cognito-sub-abc123",          // set by server
  "org_id": "org-xyz-456",                  // set by server

  // Event context (from client body)
  "analysis_id": "assess-789",
  "opportunity_count": 7,
  "active_lever_filter": "Revenue Side"     // "Revenue Side" | "Cost Side" | null
}
```

Per-event-type fields:

| Event type | Adds |
|---|---|
| `sc0red_cta_banner_expanded` | — |
| `sc0red_cta_banner_collapsed` | — |
| `sc0red_cta_clicked` | — (destination URL is a known constant, not captured per event) |
| `sc0red_cta_rendered_in_pdf` | `source: "pdf"` is required; `active_lever_filter` omitted (PDF doesn't filter) |

## Privacy review

- **PII**: `user_id` is a Cognito `sub` (opaque UUID). No email, no name, no IP address is captured in the event.
- **Opportunity content**: never captured. Only `opportunity_count` (an integer) and `active_lever_filter` (one of two constants or null).
- **Mouse tracking**: none. Only explicit button-intent events.
- **Consent**: users of Janus are authenticated B2B users under org contracts. Product analytics on UI surfaces are covered by the existing ToS. No additional consent flow required.
- **Retention**: 90 days. Long enough to see month-over-month trends, short enough to limit exposure.
- **Access**: the log group inherits the same CloudWatch IAM posture as other Janus logs — readable only by SC0RED engineering staff via SSO.

## Sample Logs Insights queries

```sql
-- 7-day funnel: rendered (proxy: clicks + expansions unique per analysis) vs clicks
fields @timestamp, event_type, analysis_id, user_id, org_id
| filter @timestamp > ago(7d)
| stats count() by event_type

-- Click-through rate per org
fields @timestamp, event_type, org_id
| filter @timestamp > ago(30d)
| stats count() as events,
        sum(event_type = 'sc0red_cta_clicked') as clicks,
        sum(event_type = 'sc0red_cta_banner_expanded') as expands
        by org_id
| sort clicks desc

-- Which analyses drive engagement
fields @timestamp, event_type, analysis_id, user_id
| filter event_type in ['sc0red_cta_banner_expanded','sc0red_cta_clicked']
| filter @timestamp > ago(30d)
| stats count_distinct(user_id) as unique_users by analysis_id
| sort unique_users desc
| limit 20

-- PDF volume over time
fields @timestamp, event_type
| filter event_type = 'sc0red_cta_rendered_in_pdf'
| filter @timestamp > ago(30d)
| stats count() by bin(1d)
```

## File impact

| File | Change |
|---|---|
| `backend/src/models/analytics_events.py` | NEW — Pydantic envelope + per-event validators |
| `backend/src/handlers/analytics_handlers.py` | NEW — `handle_post_event(event, auth_context)` |
| `backend/src/handlers/api_gateway_handler.py` | MODIFIED — one dispatch line for `POST /analytics/events` |
| `backend/src/utilities/analytics_logger.py` | NEW — thin wrapper that writes to the dedicated log group |
| `backend/tests/unit/handlers/test_analytics_handlers.py` | NEW — envelope validation, auth enrichment, logging shape |
| `backend/tests/unit/models/test_analytics_events.py` | NEW — Pydantic shape tests |
| `frontend/src/lib/analytics/emitEvent.ts` | NEW — typed `emit()` helper, uses `fetch('/api/analytics/events')` |
| `frontend/src/lib/analytics/emitEvent.server.ts` | NEW — server-side variant for PDF route, uses `backendFetch()` |
| `frontend/src/app/api/analytics/events/route.ts` | NEW — thin proxy to backend |
| `frontend/src/components/Sc0redCTABanner.tsx` | MODIFIED — adds `analysisId` + `opportunityCount` props and calls `emit()` on expand/collapse/click |
| `frontend/src/components/OpportunitiesList.tsx` | MODIFIED — passes `analysisId` + `filteredOpps.length` into the banner |
| `frontend/src/app/api/export/pdf/[analysisId]/route.ts` | MODIFIED — emits `sc0red_cta_rendered_in_pdf` after successful render |
| `frontend/src/tests/components/Sc0redCTABanner.test.tsx` | MODIFIED — asserts emit calls on expand/collapse/click |
| `frontend/src/tests/lib/analytics/emitEvent.test.ts` | NEW — client helper tests |
| `infrastructure/stacks/janus_stack.py` | MODIFIED — new `logs.LogGroup` + `grant_write` to API Lambda + env var `ANALYTICS_LOG_GROUP` |

## Risks

1. **Log volume underestimated**: if events are much higher than expected, CloudWatch cost creeps up. Mitigation — the log group retention is bounded at 90 days; at 100k events/day (order of magnitude above current use) the cost is still under $5/month.
2. **Event loss on client failure**: if the emit fetch fails (network, backend 500), the event is silently lost. Acceptable — analytics, not audit. We do not want to block the UI or retry indefinitely.
3. **Insights query quota**: CloudWatch Insights has a concurrent-query cap. At 1-2 engineers querying occasionally this is not an issue.
4. **Schema drift**: if a new event field is added without bumping `analytics_version`, older queries may return NULL for the new field. Mitigation: any schema change that removes or renames a field MUST bump the version.

## Open questions

1. **Should `banner_collapsed` be a first-class event?** Adds noise for minimal signal. Proposal says yes for symmetry; implementers can drop it if it turns out to be low-value. Low cost to keep.
2. **Do we log a synthetic `sc0red_cta_rendered_in_web` event the first time the banner is shown?** Would give us a clean denominator for expand-rate. Skipping for now — we can derive an approximate denominator from page-view logs that already exist in CloudWatch, and the bar for "first iteration measurement" is met without this.

Either question can be resolved post-deploy without breaking the event schema.
