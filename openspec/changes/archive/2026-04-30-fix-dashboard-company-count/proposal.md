## Why

The dashboard's "Recent Scans" table renders `0` in the `Companies` column for a complete portfolio scan that actually has 6 analysed companies. Reproduced on dev: the row for `https://coalescecap.com/` shows status `Complete` with `0` in the Companies column, while `GET /api/scan/d3b3c9ce-0a5b-4982-9fae-58a6588050c4` returns `status: "complete"`, `progress: 100`, `totalCompanies: 6`, six completed analyses, six portfolio companies. Clicking "View Portfolio" lands on the detail page and shows the full six.

Root cause: `frontend/src/app/(authenticated)/dashboard/page.tsx:341` renders the cell as `{scan.completedCount || 0}`. The same component, 35 lines below, already does it correctly for `DeleteScanButton`:

```tsx
// Prefer totalCompanies (cascade truth) over completedCount, which would
// underreport for in-flight scans where some links are pending.
companyCount={scan.totalCompanies || scan.completedCount}
```

The DeleteScanButton fix landed at some point with the right reasoning written down; the visible cell never got the same treatment. For this particular scan, `completed_count` is 0 or unset on the record (likely because the scan completed before the per-progress counter was wired in `sqs_handler._update_scan_progress`, or it was wiped during a delete/restore cycle), while `total_companies` correctly persists 6 from confirm time.

## What Changes

- **Frontend**: `dashboard/page.tsx` line 341 — change `{scan.completedCount || 0}` to use the same precedence the comment 35 lines below already prescribes: `{scan.totalCompanies || scan.completedCount || 0}`. For complete scans `totalCompanies` is the truth; for in-flight scans where `total_companies` is set but `completed_count` is the partial number, the in-flight row arguably wants `completedCount` shown — which is why the in-flight comment in `DeleteScanButton` exists. To preserve in-flight behaviour, the precedence should switch on status: render `completedCount` while `status !== 'complete'`, render `totalCompanies` when complete, both with `|| 0` as the floor.

## Capabilities

### New Capabilities
_(None — bug fix.)_

### Modified Capabilities
_(None.)_

## Impact

- **Modified**: `frontend/src/app/(authenticated)/dashboard/page.tsx`
- **Modified**: dashboard render test (assert `Companies` cell value for `status="complete"` with `completedCount=0` and `totalCompanies=6` → renders `6`).
- **Tests**: frontend only.
