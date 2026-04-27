## Context

`_compute_scan_progress` divides by `len(analyses)` — only records that exist. With `reserved_concurrency=3`, the last companies in a batch may not have records yet when the poll fires.

## Goals / Non-Goals

**Goals:** Progress reflects true total. Frontend doesn't show completion prematurely.
**Non-Goals:** Fixing SQS delivery timing.

## Decisions

Pass `total_companies` to `_compute_scan_progress`, use `max(total_companies, len(analyses))` as denominator. Frontend adds `analyses.length >= totalCompanies` to `allResolved` check.
