## Why

A 6-company portfolio scan shows "5 of 5 done" at 100% while the 6th company is still processing. The scan appears complete (stats visible, progress strip gone) before all companies finish. On refresh after the 6th completes, it jumps to "6 companies".

Root cause: both backend `_compute_scan_progress` and frontend `allResolved` use `analyses.length` (DynamoDB records that exist) as the denominator instead of `total_companies` (set at confirm time). When a company hasn't been picked up by the worker yet, its record doesn't exist — making 5/5 look like 100% when the true state is 5/6.

## What Changes

- **Backend**: `_compute_scan_progress` accepts `total_companies` and uses `max(total_companies, len(analyses))` as denominator
- **Frontend**: `allResolved` also requires `analyses.length >= totalCompanies`

## Capabilities

### New Capabilities
_(None — bug fix.)_

### Modified Capabilities
_(None.)_

## Impact

- **Modified**: `backend/src/handlers/scan_handlers.py`
- **Modified**: `frontend/src/app/(authenticated)/portfolio/[scanId]/PortfolioView.tsx`
- **Tests**: backend + frontend
