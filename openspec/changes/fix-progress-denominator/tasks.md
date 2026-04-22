## 1. Backend — fix _compute_scan_progress denominator

- [x] 1.1 `_compute_scan_progress` accepts `total_companies`, uses `max(total_companies, len(analyses))`
- [x] 1.2 Call site passes `total_companies`
- [x] 1.3 5 unit tests in `test_scan_progress.py` including 5/6 scenario → 83%

## 2. Frontend — fix allResolved check

- [x] 2.1 `allResolved` now requires `analyses.length >= totalCompanies`
- [x] 2.2 Test: 1 analysis resolved but totalCompanies=6 → strip visible, stats hidden

## 3. Quality gates

- [x] 3.1 Backend: ruff clean, 70 handler tests pass
- [x] 3.2 Frontend: lint + typecheck clean, 15 PortfolioView tests pass
- [ ] 3.3 Open PR, CI green, merge
