## 1. Back-navigation from analysis to portfolio

- [x] 1.1 `AnalysisHeader.tsx` — added optional `scanId` prop; renders "Dashboard / Portfolio" breadcrumb when present
- [x] 1.2 `AnalysisDetail.tsx` — passes `data.scanId` to `AnalysisHeader`
- [ ] 1.3 Test: AnalysisHeader with scanId renders portfolio link; without scanId renders no link

## 2. Stable card ordering in portfolio grid

- [x] 2.1 `PortfolioView.tsx` — sorts `analyses` by `id.localeCompare` before rendering (deterministic across polls)
- [x] 2.2 Same sort applies to both heatmap grid and "All Companies" table (both use the same `analyses` array)
- [ ] 2.3 Test: PortfolioView renders cards in consistent order regardless of API response order

## 3. Quality gates

- [x] 3.1 410 tests pass, lint + typecheck clean
- [ ] 3.2 Open PR (SC0RED/janus#163), CI pending, merge pending
