## Why

The sc0red CTA banner shipped on every opportunity detail view (`opportunities-cta-sc0red`, PRs #178, #179) but has zero instrumentation. Today we cannot answer:

- How often does someone expand the banner vs. leave it collapsed?
- How often does an expansion convert to a click on "Start the conversation"?
- Which analyses / orgs / users drive the clicks?
- Does expansion or click rate differ across environments?

Without this data we are shipping a conversion surface blind. Copy, placement, and visual treatment can only be iterated against a measured baseline; a baseline requires events.

## What Changes

### 1. Event emission from the CTA surfaces

Emit four event types from the two places the banner renders:

- `sc0red_cta_banner_expanded` — the user toggled the collapsed banner open (web)
- `sc0red_cta_banner_collapsed` — the user toggled it closed again (web, optional symmetry)
- `sc0red_cta_clicked` — the user clicked the external link, fired before navigation (web)
- `sc0red_cta_rendered_in_pdf` — a PDF export was generated that contains the CTA (server-side)

Every event carries a common envelope: `event_id`, `event_type`, `timestamp`, `user_id`, `org_id`, `analysis_id`, `opportunity_count`, `active_lever_filter`, `source` (`"web"` or `"pdf"`), and `analytics_version`.

### 2. Sink: backend endpoint → CloudWatch Logs

A new `POST /analytics/events` endpoint validates and enriches incoming events and writes them as structured JSON to a dedicated CloudWatch Log Group (`/janus/{env}/analytics-events`, 90-day retention).

Funnel queries run in **CloudWatch Logs Insights** — `stats count() by event_type`, filter by `org_id` / `analysis_id`, time-range scoped.

Rejected alternatives:
- **SaaS vendor** (PostHog/Amplitude/Segment) — premature for current scale, new vendor + secret + privacy review
- **DynamoDB events** — all four GSIs are already allocated, analytics in the same table pollutes operational queries, no native query engine for funnel math
- **AppSync mutations** — schema overhead for a write-only stream, wrong tool

### 3. Privacy posture

- **No opportunity content captured** — no titles, no rationale text, no service-mapping suggestions
- **No hover / mouse tracking** — only explicit expand / collapse / click intents
- **No IP logging** — events do not include source IP, and API Gateway access logs are not forwarded to the analytics log group
- **`org_id` sourced from JWT, not request body** — prevents spoofing via crafted requests
- **User ID == Cognito `sub`** — opaque to external observers and already present in NextAuth session

## Capabilities

### New Capabilities
- `opportunities-cta-analytics`: Event tracking for sc0red CTA banner engagement across web and PDF surfaces, backed by a CloudWatch log group queried via Logs Insights.

### Modified Capabilities
_(None — purely additive.)_

## Impact

- **New backend module**: `src/handlers/analytics_handlers.py` with a single `handle_post_event` function, routed from `api_gateway_handler.py`
- **New backend model**: `src/models/analytics_events.py` — Pydantic envelope + per-event validators
- **New route**: `POST /analytics/events` — authenticated (Cognito JWT), validates + enriches + logs
- **New frontend module**: `src/lib/analytics/emitEvent.ts` — typed client, exported helper `emit(eventType, payload)`
- **New Next.js route**: `src/app/api/analytics/events/route.ts` — thin proxy to backend via `backendFetch()`
- **Frontend wiring**: `Sc0redCTABanner.tsx` emits expand/collapse/click events via the new helper
- **PDF route**: `src/app/api/export/pdf/[analysisId]/route.ts` emits `sc0red_cta_rendered_in_pdf` after the document is generated
- **Infrastructure**: new CDK log group `/janus/{env}/analytics-events` with 90-day retention; API Lambda granted `logs:PutLogEvents` on it
- **No DynamoDB schema changes**: none
- **No frontend SDK additions**: no PostHog, no Amplitude, no Segment

## Non-Goals

- **A/B testing the CTA copy**. Scope a separate change once we have a funnel baseline.
- **Cross-page analytics**. This change is only about the sc0red CTA surface.
- **Real-time dashboards**. Logs Insights ad-hoc queries are sufficient at current volume.
- **Per-opportunity engagement** (e.g., which opportunity card was visible when the user expanded). Added later if the funnel baseline shows it matters.
- **Batching / beacon API**. At current volume (tens to low hundreds of events per day) a single `fetch()` per event is fine and keeps the code path simple.
