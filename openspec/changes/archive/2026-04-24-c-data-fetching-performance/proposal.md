# Package C: Data Fetching & Performance

**Impact**: High | **Effort**: Medium | **Priority**: After Package A (parallel with B)

## Problem

Frontend uses manual `fetch()` + `useState` for all client-side data. No request caching, no deduplication, no stale-while-revalidate. Polling runs at fixed 2-3 second intervals without backoff. Backend DynamoDB queries are unbounded — handlers load ALL records for an org with no pagination.

## Proposal

Improve data fetching on the frontend with SWR/React Query, add pagination to backend queries, and optimize polling.

## Frontend changes

### 1. SWR or React Query

Replace manual `fetch` + `useState` + `useEffect` patterns in client components with a data fetching library. Candidates:

| | SWR | React Query |
|---|---|---|
| Bundle size | ~4KB | ~12KB |
| Cache | In-memory | In-memory + persist |
| Mutations | Manual | Built-in optimistic |
| DevTools | Basic | Excellent |
| Recommendation | **Preferred** (lighter, Next.js native) | If we need mutations |

Key wins:
- Automatic request deduplication (multiple components fetching same data)
- Stale-while-revalidate (show cached data instantly, refresh in background)
- Focus revalidation (refresh when user tabs back)
- Error retry with backoff (built-in)

### 2. Polling with exponential backoff

Current: `useScanPolling` polls every 2-3 seconds forever. Proposed:
- Start at 1s, increase to 2s, 4s, 8s, cap at 15s
- Reset to 1s when progress changes
- Stop when status is `complete` or `failed`

### 3. Lazy loading for heavy components

- `ComparisonRadar` (recharts) — load only when comparison page is viewed
- `ValueChainDiagram` (@xyflow/react) — dynamic import with loading fallback
- `EbitdaTree` (ReactFlow) — same pattern

## Backend changes

### 4. DynamoDB pagination in repositories

Add `limit` and `last_key` parameters to query methods:
- `company_repository.find_by_org(org_id, limit=20, last_key=None)`
- `scan_repository.find_recent_by_org(org_id, limit=10, last_key=None)`

Return `(items, last_evaluated_key)` tuples so callers can paginate.

### 5. Paginated API endpoints

Update handlers to accept `?limit=20&cursor=xxx` query parameters:
- `GET /api/analyses` — currently returns all
- `GET /api/dashboard` — limit recent analyses + recent scans
- `GET /api/scan/{id}` — limit linked companies list

## What we DON'T do

- No infinite scroll UI (pagination buttons are fine for v1)
- No server-side caching (DynamoDB on-demand is fast enough)
- No CDN caching for API responses
- No WebSocket replacement for polling (AppSync exists but polling is simpler)

## Success criteria

- [ ] Client-side fetches use SWR (or React Query)
- [ ] Polling uses exponential backoff (1s → 15s cap)
- [ ] Heavy chart components lazy-loaded
- [ ] Backend list endpoints support `limit` + `cursor` pagination
- [ ] Dashboard loads in < 200ms for orgs with 100+ companies
- [ ] Bundle size for analysis page reduced (lazy-loaded charts)
