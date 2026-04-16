## Context

Current portfolio scan UX flow:

```
Confirm → phase='running' → ScanProgressPhase
  → portfolioPolling/portfolioRealtime watches for status='complete'
  → handlePortfolioComplete() fires
  → router.push(/portfolio/{scanId})
  → PortfolioView SSR + client poll (already shows partial results)
```

The bottleneck is that `handlePortfolioComplete` only fires when the ENTIRE scan reaches `status=complete`. The user sits on the progress bar for 5-20 minutes.

After this change:

```
Confirm → phase='running' → ScanProgressPhase (SAME AS TODAY)
  → portfolioPolling detects FIRST analyzedAt in any analysis
  → router.push(/portfolio/{scanId})                           ← NEW TRIGGER
  → PortfolioView shows:
      - progress strip ("5 of 69 done") instead of summary stats
      - completed cards + analyzing + queued cards
      - polls every 4s (existing)
  → when status='complete':
      - progress strip disappears
      - summary stats appear
```

## Goals / Non-Goals

**Goals:**
- Navigate to the portfolio page as soon as the first company result is available (typically ~30-50 seconds after confirm).
- Show a compact progress indicator on the portfolio page while the scan is running.
- Hide summary statistics until the scan is complete (partial stats are misleading).
- Preserve the existing single-company scan UX entirely.
- Reuse existing components and polling infrastructure — no new API endpoints, no new backend logic.

**Non-Goals:**
- Changing the scan progress bar component itself (`ScanProgressPhase`).
- Adding email/push notifications for scan completion. (Good idea, separate change.)
- Changing the per-company card rendering (already handles partial state).
- Modifying backend polling or AppSync behavior.
- Optimizing AI call parallelism or retry (separate change: `pipeline-error-retry`).

## Decisions

### Decision 1: Detect "first company complete" via existing poll data, not a new API

**Decision**: the `portfolioPolling` callback already receives `ScanPollResponse` with an `analyses` array. Check if any entry has `analyzedAt` set. When true, navigate.

**Why**: zero backend work. The data is already there. The check is `data.analyses?.some(a => a.analyzedAt)`.

**Alternative considered**: new backend field `first_completed_at` on the scan record. Rejected — adds backend work for something the frontend can derive from existing data.

### Decision 2: Navigate from `page.tsx`, not from the polling hook

**Decision**: the `onProgress` callback in `page.tsx` checks the raw poll data for the first `analyzedAt` and calls `router.push`. The polling hook itself doesn't change its interface — it still reports progress and terminal states.

**Why**: the polling hook (`useScanPolling`) is used in both discovery and portfolio modes. Adding portfolio-specific "first complete" logic to the hook muddies its responsibility. The page is the right place to decide "when to navigate."

**Alternative considered**: new `onFirstComplete` callback on `useScanPolling`. Rejected — adds a hook interface change for one consumer. The page can derive this from `onProgress` data.

**Implementation note**: the portfolio-mode `onProgress` callback doesn't currently receive the raw `ScanPollResponse` — it receives computed `(progress, label)`. To check `analyses`, we need either:
- (a) Extend `onProgress` to also pass the raw data
- (b) Add a new `onFirstComplete` callback (rejected above)
- (c) Use `onComplete` differently
- (d) Introduce a separate `onPollData` raw-data callback

Option (a) is the lightest change — add an optional third parameter to `onProgress`: `onProgress(progress, label, rawData?)`. The page checks `rawData?.analyses?.some(a => a.analyzedAt)` and navigates. Non-portfolio callers ignore the third arg.

### Decision 3: `PortfolioProgressStrip` is a new extracted component

**Decision**: the progress strip at the top of the portfolio page is a focused component: `PortfolioProgressStrip.tsx`. It receives `completedCount`, `totalCount`, and `visible` props. When `visible` is false, it renders nothing.

**Why**: keeps `PortfolioView.tsx` under the 360-line limit. The strip has its own visual logic (progress bar width, label, animation).

### Decision 4: Summary stats gated behind `status === 'complete'`

**Decision**: the summary stats section (risk tier counts, average score) only renders when the scan is fully complete. While running, the progress strip occupies that visual space.

**Why**: showing stats based on 5/69 companies is actively misleading — "average risk: 4.2" based on 5 data points will swing wildly as more complete. Better to show nothing than misleading data.

**Alternative considered**: show stats with a "(based on 5/69)" qualifier. Rejected — adds visual complexity and the stats still swing confusingly.

### Decision 5: "Queued" vs "Analyzing..." card state

**Decision**: cards that have no `analyzedAt`, no `error`, and no `pipelineProgress` show "Queued". Cards with `pipelineProgress > 0` show "Analyzing... (N%)". Cards with `error` show the FAILED badge (from `failed-analysis-ux`). Cards with `analyzedAt` show the full result.

**Why**: "Queued" is more honest than "Analyzing..." for 64 companies sitting in the SQS queue while only 5 are actively processing. Currently all non-complete cards show "Analyzing..." which implies active work.

### Decision 6: Existing polling cadence in PortfolioView is kept at 4 seconds

**Decision**: no change to the 4s poll interval in PortfolioView. This is already tuned for progressive updates.

**Why**: 4 seconds is a good balance — fast enough to show new completions within a few seconds, slow enough to not overload the API. AppSync real-time supplements this when available.

## Risks / Trade-offs

- **[Risk] Navigating to portfolio page with only 1/69 complete could feel empty.** → Mitigation: the progress strip anchors the page ("1 of 69 done — we're working on it"), and the grid fills over the next 10-15 minutes. User can click the one completed card immediately.
- **[Risk] The existing `portfolioPolling` completion handler fires `handlePortfolioComplete` which does `router.push(/portfolio/{scanId})`. If we navigate early, the completion handler will try to navigate AGAIN when all companies finish (redundant push to same URL).** → Mitigation: either (a) skip the final navigation if already on `/portfolio/{scanId}`, or (b) stop the polling in `page.tsx` after the first navigation. Option (b) is cleaner — once the user is on the portfolio page, PortfolioView's own polling takes over.
- **[Risk] PortfolioView SSR fetch might see 0 completed analyses if the navigation races ahead of the first completion.** → Mitigation: the first-complete check is in the poll callback, which fetches from the API. By the time it triggers, at least 1 analysis is complete in DynamoDB. The SSR page fetch happens after navigation, so it will see the same data.
- **[Trade-off] Two competing polling loops (page.tsx's portfolioPolling + PortfolioView's own poll) for a brief moment during navigation.** → Accepted: the page.tsx polling is cleaned up on unmount (existing `useEffect` cleanup). Duration is milliseconds.

## Open Questions

_(None — all questions resolved during exploration.)_
