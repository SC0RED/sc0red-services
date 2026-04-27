## 1. Back-navigation from analysis to portfolio

- [x] 1.1 `AnalysisHeader.tsx` — added optional `scanId` prop; renders "Dashboard / Portfolio" breadcrumb when present
- [x] 1.2 `AnalysisDetail.tsx` — passes `data.scanId` to `AnalysisHeader`
- [x] 1.3 Test: AnalysisHeader with scanId renders portfolio link; without scanId renders no link — `AnalysisHeader.test.tsx` lines 59, 66

## 2. Stable card ordering in portfolio grid

- [x] 2.1 `PortfolioView.tsx` — sorts `analyses` by `id.localeCompare` before rendering (deterministic across polls)
- [x] 2.2 Same sort applies to both heatmap grid and "All Companies" table (both use the same `analyses` array)
- [x] 2.3 Test: PortfolioView renders cards in consistent order regardless of API response order — `PortfolioView.test.tsx` line 175

## 3. Quality gates

- [x] 3.1 410 tests pass, lint + typecheck clean
- [x] 3.2 PR #163 merged to `development`; CI green
