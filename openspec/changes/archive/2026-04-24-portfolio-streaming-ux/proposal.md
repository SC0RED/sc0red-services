## Why

For portfolio scans with 5+ companies, the current UX shows a progress bar on the `/scan/new` page for the entire duration of the analysis run (5-20 minutes for large portfolios). The progress bar crawls, shows misleading intermediate percentages, and blocks the user from interacting with results until every company finishes. The user stares at a screen they can't act on.

The portfolio view at `/portfolio/{scanId}` already handles partial results — it renders completed cards alongside "Analyzing..." placeholders and polls for updates. But the user never sees it until ALL companies finish, because the progress page holds them hostage.

Single-company scans (30-45 seconds) work well with the progress bar pattern — the wait is short and the user lands on a complete analysis page. This change only affects the portfolio flow.

## What Changes

### Phase 1 → Phase 2 transition: progress bar until first company completes

After the user confirms portfolio companies, the existing `ScanProgressPhase` (progress bar) renders as today. But instead of waiting for ALL companies to finish, the progress-bar page watches for the **first company to complete** (`analyzedAt` appears in any analysis). Once that happens, it navigates to `/portfolio/{scanId}`.

Trigger: `portfolioPolling` / `portfolioRealtime` callback detects at least one analysis with `analyzedAt` → `router.push(/portfolio/{scanId})`.

### Phase 2: Portfolio grid with progress strip

The portfolio page renders immediately with a mix of completed cards, "Analyzing..." cards, and "Queued" cards. At the top, instead of the summary stats section, a thin progress strip shows `"5 of 69 done"` with a progress bar. Summary stats (risk tier counts, average score) are hidden while the scan is running.

### Phase 3: Complete — progress strip removed, stats appear

When the scan status transitions to `complete`, the progress strip disappears and the summary stats section renders. This is the existing PortfolioView behavior with the stats always visible — now gated behind `status === 'complete'`.

### Single-company scan: no change

The `ScanProgressPhase` → `router.push(/analysis/{id})` flow is completely unchanged. The new transition only applies when `mode === 'portfolio'`.

## Capabilities

### New Capabilities
- `portfolio-streaming-results`: progressive rendering of portfolio analysis results as they arrive, with a compact progress indicator during analysis and deferred summary statistics until completion.

### Modified Capabilities
_(No existing specs to modify.)_

## Impact

- **Modified**: `frontend/src/app/(authenticated)/scan/new/page.tsx` — `portfolioPolling` and `portfolioRealtime` callbacks: detect first-company-complete, navigate to portfolio page instead of waiting for full completion.
- **Modified**: `frontend/src/app/(authenticated)/portfolio/[scanId]/PortfolioView.tsx` — add a progress strip component at the top when scan is running; conditionally hide summary stats section until `status === 'complete'`.
- **New**: `frontend/src/components/scan/PortfolioProgressStrip.tsx` — thin progress bar with "N of M done" label, appears above the heatmap grid while running.
- **Modified**: `frontend/src/lib/hooks/useScanPolling.ts` — portfolio-mode polling needs a new callback for "first company complete" (or existing `onProgress` callback carries enough data to detect it at the call site).
- **No backend changes**: the API already returns partial results via `GET /api/scan/{id}`. The poll response includes `analyses` with per-company status. Nothing new is needed server-side.
- **No infrastructure changes**.
- **Tests**: Vitest + RTL tests for new transition logic, progress strip rendering, stats visibility gating.
