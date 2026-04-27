## Why

Two usability issues after the portfolio streaming UX shipped:

1. **No back-navigation from analysis to portfolio**: When a user clicks a completed company card on the portfolio page, the analysis detail page has no way to return to the portfolio — only the browser back button. The failed-analysis view already has a "Back to Portfolio" link (from `failed-analysis-ux`), but the successful analysis view doesn't. Inconsistent and unprofessional.

2. **Cards dance on every progress update**: The heatmap grid reorders company cards on every poll cycle. Root cause: `company_repo.get_by_ids()` calls DynamoDB `BatchGetItem` which does NOT guarantee return order. Each poll returns analyses in arbitrary order → React re-renders the grid → cards jump around. Visually jarring — the user loses track of which company they were looking at.

## What Changes

- **Back to portfolio link**: When `data.scanId` is present on the analysis detail page, show a "Back to Portfolio" link above the header (matching the existing pattern in `FailedAnalysisView`). Single-company scans (no `scanId`) don't show the link.
- **Stable card order**: Sort the `analyses` array in `PortfolioView` by a stable key before rendering. Sort completed analyses first (by `companyName` alphabetically), then in-progress (by `id`), then queued (by `id`). This order is deterministic across polls.

## Capabilities

### New Capabilities
_(None — polish on existing features.)_

### Modified Capabilities
_(None.)_

## Impact

- **Modified**: `frontend/src/components/analysis/AnalysisHeader.tsx` — add "Back to Portfolio" link when scanId is present
- **Modified**: `frontend/src/app/(authenticated)/analysis/[analysisId]/AnalysisDetail.tsx` — pass scanId to AnalysisHeader
- **Modified**: `frontend/src/app/(authenticated)/portfolio/[scanId]/PortfolioView.tsx` — sort analyses before rendering
- **No backend changes**
