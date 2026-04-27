## 1. Polling hook: expose raw poll data to callers

- [x] 1.1 Extended `PortfolioCallbacks.onProgress` with optional third `rawData?: ScanPollResponse`; `handlePortfolioPoll` passes `data` as third arg
- [x] 1.2 Existing callers unaffected (third arg is optional)
- [x] 1.3 Updated existing portfolio-mode test to assert third arg is defined with correct analyses array

## 2. Navigate to portfolio page on first company completion

- [x] 2.1 Added `hasNavigatedToPortfolio` ref to prevent double-navigation
- [x] 2.2 Added `handlePortfolioProgress` callback that checks `rawData?.analyses?.some(a => a.analyzedAt)` and navigates
- [x] 2.3 Hooks clean up on component unmount (existing `useEffect` cleanup) — no explicit stop needed before `router.push`
- [x] 2.4 Existing `handlePortfolioComplete` (`status=complete`) remains as fallback in `portfolioPolling` and `portfolioRealtime`
- [x] 2.5 Test: poll with one `analyzedAt` → asserts `mockPush('/portfolio/s-1')`
- [x] 2.6 Test: poll with zero `analyzedAt` → asserts `mockPush` NOT called with portfolio URL

## 3. Handle realtime path for first company completion

- [x] 3.1 Realtime hook aggregates per-company events but doesn't expose individual completions — first-complete detection handled by polling path (fires within 1-2s). Realtime `onComplete` (all done) remains as fallback.
- [x] 3.2 Existing `onComplete` callback unchanged — fires when all companies reach `complete`, navigates if polling didn't already.

## 4. PortfolioProgressStrip component

- [x] 4.1-4.2 Created `PortfolioProgressStrip.tsx` (58 lines): thin 4px progress bar + "N of M done" label + CSS transition
- [x] 4.3 4 tests: correct label/percentage, hidden when `visible=false`, hidden when `totalCount=0`, 100% when all done

## 5. Wire PortfolioProgressStrip into PortfolioView

- [x] 5.1-5.3 `PortfolioProgressStrip` wired with `completedCount` (analyzedAt + error), `totalCount`, `visible={isRunning}`
- [x] 5.4 Tests: running scan shows "1 of 2 done"; complete scan hides strip

## 6. Hide summary stats while scan is running

- [x] 6.1 Stats section wrapped in `{!isRunning && (...)}` — only renders when `scan.status === 'complete'`
- [x] 6.2 Old "updating..." indicator replaced by progress strip; `pending` variable removed
- [x] 6.3 Tests: running scan → "Avg Risk Score" not in DOM; complete scan → visible

## 7. Distinguish "Queued" from "Analyzing..." on cards

- [x] 7.1-7.3 Cards with `pipelineProgress === 0` show "Queued" (muted, opacity 0.6); cards with `pipelineProgress > 0` show "Analyzing..." (blue); added `pipelineProgress` + `pipelineLabel` to `ScanAnalysis` type
- [x] 7.4 Tests: pending card with no progress → "Queued"; card with pipelineProgress=30 → "Analyzing..."

## 8. Quality gates

- [x] 8.1 Lint clean
- [x] 8.2 Typecheck clean
- [x] 8.3 409 tests pass
- [x] 8.4 No backend changes
- [x] 8.5 PortfolioView.tsx: 350 lines; PortfolioProgressStrip.tsx: 58 lines — both under limits
- [x] 8.6 Architecture review: 2 CRITICALs fixed (stale `phase` closure → `phaseRef`; double navigation → `hasNavigatedToPortfolio` guard in `handlePortfolioComplete`). MEDIUM (errors counted as "done") accepted — failed analyses ARE resolved from the user's perspective.

## 9. Deploy + verify

- [x] 9.1 Open PR against `development`; CI green (PRs #159, #160, #161, #162, #163, #164 — all merged)
- [x] 9.2 Deploy to dev; portfolio scan with 10+ companies verified:
  - Progress bar shows until first company completes
  - Navigates to portfolio page automatically (AppSync onFirstComplete — #160)
  - Progress strip shows "N of M done" and updates (per-company complete/failed events — #161)
  - Cards render without duplicates and summary stats appear on completion (#162)
  - totalCompanies used for portfolio count (#164)
- [x] 9.3 Verified single-company scan unchanged (progress bar → analysis page) — covered by E2E suite
- [x] 9.4 Promoted `development` → `testing` → `production` via merged PRs above
