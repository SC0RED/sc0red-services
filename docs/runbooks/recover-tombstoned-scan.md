# Runbook — Recover a tombstoned scan / analysis

> **Audience:** on-call engineers responding to a "user accidentally deleted X, can we restore it?" support ticket.
>
> **Window:** 90 days from `deleted_at` (user-facing recovery window).
> The underlying DynamoDB TTL is set to 95 days, so records at the edge
> of the window often survive a few extra days — but treat 90 days as
> the contract. After 90 days, escalate to the data-replay procedure
> (separate runbook, future).

This runbook applies to records soft-deleted after the
`soft-delete-recovery` change shipped (PR #206 onward). Older deletes
are hard-deleted and are NOT recoverable through this path.

When the [Recently Deleted admin UI](../../openspec/changes/recently-deleted-admin-ui/proposal.md)
ships (Phase 2), self-serve recovery will replace this engineer-assisted
flow for typical cases. Until then — and as the escape hatch when the
UI is broken or the affected admin is locked out — use this runbook.

## TL;DR

1. **Identify** what was deleted (a single analysis vs. a whole scan).
2. **Check it's recoverable** — `deleted_at` set, `ttl` in the future.
3. **Restore in this exact order:** assessments → companies → links → scan.
4. **Verify** by reading through the API as the affected user.

Wrong order = a half-restored scan that looks like an orphan.

---

## 0. Prerequisites

- AWS CLI configured for the affected environment (`development` /
  `testing` / `production`).
- The DynamoDB table name: `janus-{env}` (e.g. `janus-production`).
- Region: `us-east-1`.
- Either the `analysis_id` or the `scan_id` from the user. If the user
  only has the company name, fetch the org's recently-deleted records
  from the table (Step 1 below).

Throughout this runbook, set:

```bash
TABLE=janus-production
REGION=us-east-1
```

---

## 1. Identify the deleted records

### 1a. The user gave you an analysis id

```bash
aws dynamodb get-item \
  --region "$REGION" \
  --table-name "$TABLE" \
  --key "$(jq -nc --arg id "$ANALYSIS_ID" '{pk:{S:("COMPANY#" + $id)}, sk:{S:"COMPANY#METADATA"}}')"
```

Confirm the response contains `deleted_at` (item is tombstoned, recoverable)
and `ttl` (epoch seconds — recoverable until that time).

### 1b. The user gave you a scan id

```bash
aws dynamodb get-item \
  --region "$REGION" \
  --table-name "$TABLE" \
  --key "$(jq -nc --arg id "$SCAN_ID" '{pk:{S:("SCAN#" + $id)}, sk:{S:"SCAN#METADATA"}}')"
```

### 1c. The user only knows the company name + their org

Query the org's GSI for recently-tombstoned companies:

```bash
aws dynamodb query \
  --region "$REGION" \
  --table-name "$TABLE" \
  --index-name GSI1 \
  --key-condition-expression "GSI1PK = :pk" \
  --filter-expression "attribute_exists(deleted_at)" \
  --expression-attribute-values "$(jq -nc --arg org "$ORG_ID" '{":pk":{S:("ORG#" + $org)}}')"
```

Eyeball the `company_name` + `deleted_at` to find the right record.

---

## 2. Check the TTL window

```bash
python3 -c "import sys, time; ttl=int(sys.argv[1]); print(f'expires in {(ttl-time.time())/86400:.1f} days')" "$TTL"
```

If `expires in -X days`: TTL has fired or is about to. Recovery is racing
the eviction — proceed quickly, and expect `ConditionalCheckFailedException`
on writes (the repo `restore()` calls are guarded). If that happens, the
record is gone; escalate.

---

## 3. Restore — in dependency order

> **Critical.** Restore in this exact order. Inverting the order leaves
> the user looking at a half-restored mess: a live scan with no live
> companies, or a live company with no live assessment data, etc.

### Order (bottom-up):

```
1. Assessment metadata    pk = ASSESSMENT#{id}, sk = ASSESSMENT#METADATA
2. Company metadata       pk = COMPANY#{id},    sk = COMPANY#METADATA
3. Scan→company link      pk = SCAN#{scan_id},  sk = COMPANY#{company_id}
4. Scan metadata          pk = SCAN#{id},       sk = SCAN#METADATA
```

For a portfolio scan with N companies, you restore N assessments + N companies
+ N links + 1 scan, in that order.

For a single standalone analysis (no parent scan), only steps 1 and 2 apply.

### 3a. Find every assessment for the company

```bash
aws dynamodb query \
  --region "$REGION" \
  --table-name "$TABLE" \
  --index-name GSI3 \
  --key-condition-expression "GSI3PK = :pk" \
  --expression-attribute-values "$(jq -nc --arg c "$COMPANY_ID" '{":pk":{S:("COMPANY#" + $c)}}')"
```

For each `id` in the response with `deleted_at` set, restore the
assessment metadata. Sub-records (RISK#, OPP#, EBITDA_TREE, VALUE_CHAIN,
DOC#) were never tombstoned — restoring the metadata is enough.

### 3b. Restore each assessment

```bash
aws dynamodb update-item \
  --region "$REGION" \
  --table-name "$TABLE" \
  --key "$(jq -nc --arg id "$ASSESSMENT_ID" '{pk:{S:("ASSESSMENT#" + $id)}, sk:{S:"ASSESSMENT#METADATA"}}')" \
  --update-expression "REMOVE deleted_at, #ttl" \
  --expression-attribute-names '{"#ttl":"ttl"}' \
  --condition-expression "attribute_exists(pk)"
```

The `condition-expression` mirrors the `require_exists=True` guard the
application uses — if TTL evicted the row between Step 1 and now, this
fails fast rather than silently writing an empty shell.

### 3c. Restore the company (analysis)

```bash
aws dynamodb update-item \
  --region "$REGION" \
  --table-name "$TABLE" \
  --key "$(jq -nc --arg id "$COMPANY_ID" '{pk:{S:("COMPANY#" + $id)}, sk:{S:"COMPANY#METADATA"}}')" \
  --update-expression "REMOVE deleted_at, #ttl" \
  --expression-attribute-names '{"#ttl":"ttl"}' \
  --condition-expression "attribute_exists(pk)"
```

For a standalone analysis, **stop here**. The user can now see the
analysis in `/analyses` and on the dashboard.

### 3d. Restore the scan→company link

```bash
aws dynamodb update-item \
  --region "$REGION" \
  --table-name "$TABLE" \
  --key "$(jq -nc --arg s "$SCAN_ID" --arg c "$COMPANY_ID" '{pk:{S:("SCAN#" + $s)}, sk:{S:("COMPANY#" + $c)}}')" \
  --update-expression "REMOVE deleted_at, #ttl" \
  --expression-attribute-names '{"#ttl":"ttl"}' \
  --condition-expression "attribute_exists(pk)"
```

### 3e. Restore the scan metadata (last)

```bash
aws dynamodb update-item \
  --region "$REGION" \
  --table-name "$TABLE" \
  --key "$(jq -nc --arg id "$SCAN_ID" '{pk:{S:("SCAN#" + $id)}, sk:{S:"SCAN#METADATA"}}')" \
  --update-expression "REMOVE deleted_at, #ttl" \
  --expression-attribute-names '{"#ttl":"ttl"}' \
  --condition-expression "attribute_exists(pk)"
```

---

## 4. Verify

### 4a. Confirm `deleted_at` and `ttl` are absent on every restored row

For each row touched in Step 3, re-run the matching `get-item` from
Step 1 and confirm `deleted_at` and `ttl` are not in the response.

### 4b. Read through the API as the affected user

If you can stand up a test session with the affected user's credentials
(or use a same-org admin):

- `GET /api/dashboard` — restored scan reappears in `recentScans`.
- `GET /api/analyses` — restored analyses reappear.
- `GET /api/scan/{scan_id}` — portfolio view loads.
- `GET /api/analysis/{company_id}` — analysis detail loads with the
  original risk scores / opportunities / EBITDA tree.

### 4c. Sanity-check the data is real

A common failure mode of bypassing the `condition-expression` guard is
to write an empty `{pk, sk}` shell that looks restored to the read
filter (no `deleted_at` → live) but has lost every business field.
Confirm the restored record has:

- `company_name` non-empty
- `org_id` matches the user's org
- `risk_tier` / `overall_risk_score` populated (for fully-analyzed records)

If a field that should be there is missing, the row is a shell —
record the failure, escalate. Do not "fix it up" by writing missing
fields manually; that's how data corruption ships.

---

## 5. Communicate back to the user

Template:

> Hi [user], we restored your [scan / analysis "name"] (deleted at
> [timestamp]). It should appear in [Recent Scans / your /analyses
> list] now. Restoration was a one-time intervention; in the future,
> deletes will be self-serve via the Recently Deleted admin page
> we're shipping next.

If multiple analyses were restored, list them.

---

## 6. Escalation paths

| Symptom | Action |
|---|---|
| `ConditionalCheckFailedException` on any restore step | TTL has evicted the row. Recovery impossible. Inform user. Open data-replay request if applicable. |
| Restored scan shows zero analyses on the portfolio page | You restored the scan but missed the link records. Re-run Step 3d for each linked company. |
| Restored analysis has no risk scores / EBITDA tree | Sub-records went missing somehow (shouldn't happen — they're never tombstoned). Capture details, file an incident. |
| User reports a delete you can't find tombstoned | Either it's older than 90 days (TTL evicted) or it pre-dates the soft-delete change. Inform user; not recoverable. |
| The restore step succeeded but the user still doesn't see the record | Cache / propagation delay. Wait 60s, retry. If still missing, capture the affected ids and escalate. |

---

## 7. Why the order matters (background)

A scan delete tombstones four layers in this dependency order:

```
scan                ← top
  ├── scan→company link (per company)
  └── company       ← analysis surface
        └── assessment metadata
              ├── risk scores
              ├── opportunities
              ├── EBITDA tree
              ├── value chain
              └── documents
```

Live reads filter `deleted_at`. Each layer has its own visibility:

- The dashboard's "recent scans" list reads through `find_recent_by_org`
  on `scan_repository`. Scan visibility is gated by the **scan**
  metadata's `deleted_at`.
- The portfolio page loads `get_scan_companies(scan_id)` — visibility
  of each company card is gated by the **link**'s `deleted_at`.
- The analysis detail page reads `get_by_id(company_id)` — visibility
  is gated by the **company**'s `deleted_at`.
- `find_by_company(company_id)` on `assessment_repository` — visibility
  is gated by the **assessment**'s `deleted_at`. Sub-records (risk
  scores, etc.) are gated transitively through the parent assessment.

If you restore the scan first (top of the dependency), the user sees
the scan in their list, clicks through, and finds an empty portfolio
because every link is still tombstoned. Bad UX, looks broken.

Restoring bottom-up (assessment → company → link → scan) means at every
intermediate step nothing is half-visible — the scan only reappears
once everything beneath it is already live.

---

## 8. After running this runbook

- File a brief incident note: who deleted it, who restored it, when, why.
  Goes in the team's standard incident log.
- If the same user keeps tripping accidental deletes, that's a UX signal
  — flag it for the Phase 2 admin UI design review.
- Once Phase 2 ships and is stable, this runbook becomes the escape
  hatch only. Most recoveries should go through the admin UI.
