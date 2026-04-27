## Context

Two small UX issues from the portfolio streaming feature (#159).

## Goals / Non-Goals

**Goals:**
- Consistent back-navigation from analysis detail to portfolio
- Stable card ordering in the portfolio grid during live updates

**Non-Goals:**
- Changing the analysis detail page layout
- Adding sort controls to the portfolio page

## Decisions

### Decision 1: Sort by completion state, then alphabetically by name, then by id

Sorting purely alphabetically would mix completed and in-progress cards. Better UX: group completed cards first (the ones the user wants to click into), then in-progress, then queued. Within each group, sort alphabetically by `companyName` (falls back to `id` when names are identical or absent).

### Decision 2: Sort in the frontend, not the backend

The backend returns `analyses` from DynamoDB `BatchGetItem` in arbitrary order. Adding `ORDER BY` would require a query change. Sorting in the frontend is simpler, keeps the API generic, and the sort is trivial (N < 300).

### Decision 3: AnalysisHeader receives scanId, not a separate BackLink component

The header already renders the company name and breadcrumb area. Adding the portfolio link there keeps the visual hierarchy consistent with `FailedAnalysisView`.
