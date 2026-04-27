## 1. Fix class matching in scrape_url

- [x] 1.1 Replaced substring regex with exact token matching via set intersection + html/body guard
- [x] 1.2 blinkeye.com: 5579 chars (was 0)
- [x] 1.3 perotjain: 1271, accesshealthcare: 4077, testfit: 6110 — no regression

## 2. Tests

- [x] 2.1 Unit test: element with class `"sidebar"` is removed
- [x] 2.2 Unit test: element with class `"no-sidebar"` is NOT removed
- [x] 2.3 Unit test: `<body class="sidebar">` is NOT removed (structural guard)

## 3. Quality gates

- [x] 3.1 Ruff + format clean
- [x] 3.2 730 tests pass
- [x] 3.3 Open PR, CI green, merge (PR #167, commit 0dc5590)
