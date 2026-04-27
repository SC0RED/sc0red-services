## Why

Today the portfolio scan view renders cards progressively as workers pick up SQS messages — at t=0 the page is sparse, and cards pop in one-by-one as DynamoDB `companies` records are created. A 50-company scan looks chaotic for the first 30–60 seconds: the user has no view of total scope, the layout shifts continuously, and a "Queued" card is visually almost identical to a "Scanning" card so the user can't tell what's actually happening.

The data to fix this already exists. At scan-confirm time every company is assigned a UUID and a `scan_company` link is written to DynamoDB; the missing piece is that `handle_scan_get` only returns analyses for companies with full `companies`-table records, silently filtering out the not-yet-started ones. The frontend has no choice but to show what the API returns.

## What Changes

- **API contract**: `analyses[]` from `GET /scan/{id}` always has length `total_companies`. Each entry carries an explicit `state: "pending" | "scanning" | "done" | "failed"`. Pending entries include `companyName` + `companyUrl` but null score/risk fields.
- **Backend storage**: `scan_company` link records gain `company_url` and `order_index` fields (written at confirm time). Reads fall back gracefully when older records lack them.
- **Backend handler**: `handle_scan_get` merges `scan_companies` links with `companies` records into the unified `analyses[]`. Two backend-internal states ("no record yet" + "record but `pipeline_progress=0`") collapse into one UI state called `pending`.
- **Frontend rendering**: `PortfolioView` and the bottom "All Companies" table become state-driven — visual treatment is selected from the `state` field, not inferred from null checks on `overallRiskScore` / `analyzedAt` / `pipelineProgress`.
- **Frontend visual**: scanning cards show a pulsing dot + `pipelineLabel` (e.g. "Profiling risk..."). No percentage and no progress bar — the pipeline has 6 discrete steps, so a bar would jump in chunks and imply false precision.
- **Frontend ordering**: cards sort by `order_index` (submission order, frozen). Cards never move once rendered; status changes happen on the card.
- **Frontend a11y**: pulse animation respects `prefers-reduced-motion`. A single shared CSS keyframe so 50–200 simultaneous cards aren't a perf concern.

**Out of scope** (called out so reviewers don't ask):
- Per-card progress percentage / linear bar — rejected during exploration; the 6-step pipeline can't be honestly mapped to a smooth percentage.
- Reordering cards by status during a run — rejected; violates the stability promise.
- "Stuck pending" warning for companies a worker never picks up — deferred to a follow-up change. After this change, stuck companies sit visibly on Pending instead of being silently absent (better than today, but a "stale > N min" affordance is its own design).
- Re-design of the top progress strip — `PortfolioProgressStrip` is unchanged.

## Capabilities

### New Capabilities
None. This is a UI/API improvement to existing portfolio scan behavior.

### Modified Capabilities
- `portfolio-streaming-results`: the requirement that the portfolio page shows "1 completed card and 68 queued/analyzing cards" implicitly assumes cards are rendered for not-yet-picked-up companies. In practice this only became true once a worker created the record. This change makes that requirement literal and adds an explicit `state` contract.
- `async-portfolio-scan`: the `scan_company` link record gains `company_url` and `order_index` fields. The `GET /scan/{id}` response shape adds the `state` discriminator to each analysis entry.

## Impact

**Backend code**:
- `backend/src/repositories/dynamodb/scan_repository.py` — extend `link_company()` signature; backward-compatible reads.
- `backend/src/handlers/scan_handlers.py` — refactor `handle_scan_get` and the helper `build_company_summary` boundary; possibly split if it crosses 400 lines.
- `backend/src/handlers/analysis_handlers.py` — `build_company_summary` adds `state`.
- New unit tests for state transitions and the migration-fallback path.

**Frontend code**:
- `frontend/src/lib/types/api.ts` — add `state` and `orderIndex` to `ScanAnalysis`.
- `frontend/src/app/(authenticated)/portfolio/[scanId]/PortfolioView.tsx` — state-driven card + table rendering, sorted by `orderIndex`.
- New `prefers-reduced-motion`-aware pulse keyframe.
- Vitest tests for each state's render + the reduced-motion path.

**API contract**:
- `analyses[].state` is a new field — additive, not breaking. Existing clients that ignore it keep working.
- `analyses[]` length now equals `total_companies` from t=0 instead of growing — clients that depend on the growth pattern (none today) would break, but this is the desired behavior.

**Migration**:
- In-flight scans at deploy time have `scan_company` link records without `company_url` / `order_index`. Reads fall back: pending entries for those scans render without URL and sort by `company_id`. The compatibility path drops once those scans drain.

**Quality gates**: ruff, pyright, pytest (≥ 95% coverage), npm lint, tsc, vitest, architecture-reviewer agent, E2E suite.
