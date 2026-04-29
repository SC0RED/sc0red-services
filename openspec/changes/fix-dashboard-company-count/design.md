## Context

The dashboard's `Companies` cell uses `scan.completedCount || 0`, which falls back to `0` for any complete scan whose record didn't get a `completed_count` update written (legacy records pre-counter, or records modified during the delete/restore cycles where `completed_count` was wiped while `total_companies` survived). The same component's `DeleteScanButton` 35 lines below already documented and applied the right precedence — `scan.totalCompanies || scan.completedCount` — but the cell was missed in that fix.

## Goals / Non-Goals

**Goals:** Complete scans render the confirmed total. In-flight scans continue to render the running counter so users see progress mid-stream.
**Non-Goals:** Unifying `completed_count` and `total_companies` storage. Refactoring scan-progress write paths.

## Decisions

**Status-aware precedence in the rendered cell**, not a flat `totalCompanies || completedCount`. For terminal scans (`status === 'complete'` or `'failed'`) the count we want is the cascade truth — `total_companies` is set at confirm time and survives every later state. For in-flight scans (`pending`, `discovering`, `awaiting_confirmation`, `running`) we want `completed_count` because the user wants to see "3 of 6 done" tick upward, not a static "6". A flat precedence would render `6` for an in-flight scan that's actually 0/6 done, regressing the live-progress UX.

**Extract `displayedCompanyCount(scan)` to a shared helper** instead of duplicating the precedence in two consumers. The bug is precisely that the dashboard cell and `DeleteScanButton` drifted because the rule lived in two places. Both consumers import the helper; the next consumer (any future scan-table renderer) gets it for free.
