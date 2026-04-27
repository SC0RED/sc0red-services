# SC0RED CTA Analytics — Logs Insights Queries

Reference queries for the `opportunities-cta-analytics` event stream. Run them in
**CloudWatch Logs Insights** against the per-environment log group:

| Environment | Log group |
|---|---|
| Development | `/janus/development/analytics-events` |
| Testing | `/janus/testing/analytics-events` |
| Production | `/janus/production/analytics-events` |

Retention is 90 days. Each event is a single JSON line; the fields below are
already top-level so you can `fields ...` directly without `parse @message`.

## Event envelope

Every event carries the same envelope. Per-event-specific fields are listed in
`openspec/changes/archive/<dated>-opportunities-cta-analytics/design.md` once
the change is archived; until then see `openspec/changes/opportunities-cta-analytics/design.md`.

| Field | Type | Source | Notes |
|---|---|---|---|
| `event_id` | UUID v4 | client | Unique per emission |
| `event_type` | enum | client | One of `sc0red_cta_banner_expanded`, `sc0red_cta_banner_collapsed`, `sc0red_cta_clicked`, `sc0red_cta_rendered_in_pdf` |
| `timestamp` | ISO 8601 | client | Set when the user interacted (web) or render completed (PDF) |
| `analytics_version` | string | client | `"1"` today; bumped on schema break |
| `source` | `"web"` \| `"pdf"` | client | Disambiguates the surface |
| `user_id` | Cognito sub | **server** | Enriched from the JWT — body value ignored |
| `org_id` | UUID | **server** | Enriched from the JWT — body value ignored |
| `analysis_id` | UUID | client | The analysis being viewed / exported |
| `opportunity_count` | integer | client | Number of opportunities visible at emission time (web: post-filter; PDF: total rendered) |
| `active_lever_filter` | `"Revenue Side"` \| `"Cost Side"` \| `null` | client | Web only; `null` for PDF |

## Running a query

1. Open the AWS console → CloudWatch → **Logs Insights**.
2. In the log-group selector, pick `/janus/<env>/analytics-events`.
3. Set a time range (top-right).
4. Paste a query below into the editor.
5. Click **Run query**.

The CLI equivalent is `aws logs start-query` then `aws logs get-query-results`,
but the console UI is easier for ad-hoc work.

## Q1 — 7-day event mix

Sanity-check that all four event types are landing.

```sql
fields @timestamp, event_type, analysis_id, user_id, org_id
| filter @timestamp > ago(7d)
| stats count() by event_type
```

Expected: four rows, one per `event_type`. If a row is missing, that surface
isn't emitting in the selected window.

## Q2 — Click-through rate per org

Per-org funnel over the last 30 days: total events, `sc0red_cta_clicked`,
and `sc0red_cta_banner_expanded`. Sorted by clicks descending.

```sql
fields @timestamp, event_type, org_id
| filter @timestamp > ago(30d)
| stats count() as events,
        sum(event_type = 'sc0red_cta_clicked') as clicks,
        sum(event_type = 'sc0red_cta_banner_expanded') as expands
        by org_id
| sort clicks desc
```

Click-through-rate = `clicks / expands` (computed in your head or a sheet —
Logs Insights has no division operator in `stats`).

## Q3 — Which analyses drive engagement

Top 20 analyses by unique-user engagement (expand or click) over 30 days.
Useful for spotting which company analyses are getting the most attention.

```sql
fields @timestamp, event_type, analysis_id, user_id
| filter event_type in ['sc0red_cta_banner_expanded','sc0red_cta_clicked']
| filter @timestamp > ago(30d)
| stats count_distinct(user_id) as unique_users by analysis_id
| sort unique_users desc
| limit 20
```

## Q4 — PDF render volume over time

Daily count of `sc0red_cta_rendered_in_pdf` events. Each row is one rendered
PDF — a proxy for how often the analysis export feature is used.

```sql
fields @timestamp, event_type
| filter event_type = 'sc0red_cta_rendered_in_pdf'
| filter @timestamp > ago(30d)
| stats count() by bin(1d)
```

## Tips

- **Time range matters more than you think**: Insights scans every byte in the
  range, so pick the smallest window that answers your question.
- **`stats count_distinct(...)`** is bounded — for cardinalities above ~10k it
  returns an estimate, not an exact value. At our current volume that's irrelevant.
- **Filter early**: put narrow `filter` clauses (`org_id = "..."`) before
  `stats` — Insights pushes them down.
- **Saving queries**: Insights has a "Save" button. Save the four queries above
  with names like `cta-funnel-7d`, `cta-ctr-by-org-30d` so they're one click away.

## Privacy & access

- Log group is read-restricted via IAM; Janus engineers only.
- No PII beyond Cognito `sub` (opaque UUID) is captured. No email, no IP, no
  page content.
- Retention is 90 days. Don't relax this without a privacy review.
