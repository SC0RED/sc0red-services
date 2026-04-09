# Tasks: Data Fetching & Performance

## PR 1: Frontend — SWR, polling backoff, lazy loading

### SWR setup
- [x] Install SWR dependency
- [x] Create shared fetcher utility for SWR

### Polling with exponential backoff
- [x] Update useScanPolling hook with exponential backoff (1s → 2s → 4s → 8s → 15s cap, reset on progress change)

### Lazy loading heavy components
- [x] Lazy load ComparisonRadar (recharts) with dynamic import
- [x] Lazy load ValueChainDiagram (@xyflow/react) with dynamic import
- [x] EbitdaTree already lazy-loaded (EbitdaSection.tsx line 7)

## PR 2: Backend — DynamoDB pagination

### Repository pagination
- [x] Add limit + last_key params to company_repository.find_by_org() (PR #124)
- [x] Add limit + last_key params to scan_repository.find_recent_by_org() (PR #124)
- [x] Return (items, last_evaluated_key) tuples (PR #124)

### API pagination
- [x] Update GET /api/analyses to accept ?limit=&cursor= params
- [x] Update GET /api/dashboard — loads all for stats, limits recent items
- [x] Add pagination tests
