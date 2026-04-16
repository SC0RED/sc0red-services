## 1. Back-navigation from analysis to portfolio

- [ ] 1.1 In `AnalysisHeader.tsx`, add optional `scanId` prop; when present, render a "Back to Portfolio" link above the company name
- [ ] 1.2 In `AnalysisDetail.tsx`, pass `data.scanId` to `AnalysisHeader`
- [ ] 1.3 Test: AnalysisHeader with scanId renders portfolio link; without scanId renders no link

## 2. Stable card ordering in portfolio grid

- [ ] 2.1 In `PortfolioView.tsx`, sort `analyses` before rendering: by `id` ascending (stable across polls since IDs are UUIDs assigned at confirm time)
- [ ] 2.2 Apply the same sort to the "All Companies" table below the grid
- [ ] 2.3 Test: PortfolioView renders cards in consistent order regardless of API response order

## 3. Quality gates

- [ ] 3.1 `npm run lint && npx tsc --noEmit && npm test` — all green
- [ ] 3.2 Open PR, CI green, merge
