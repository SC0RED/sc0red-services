## Why

blinkeye.com (Blink Technologies, a Perot Jain portfolio company) consistently fails with "Insufficient content scraped" — even on reanalysis with uploaded documents. The scraper returns 0 bytes of text despite the site being a standard server-rendered WordPress page.

Root cause: `scrape_url` removes elements by class name using substring regex:
```python
for cls in ["nav", "footer", "header", "sidebar", "cookie", "popup"]:
    for el in soup.find_all(class_=re.compile(cls, re.IGNORECASE)):
        el.decompose()
```

blinkeye.com's `<body>` tag has class `no-sidebar`. The regex `re.compile("sidebar", re.IGNORECASE)` matches `"sidebar"` inside `"no-sidebar"` → **the entire `<body>` is decomposed** → text length = 0 → pipeline fails.

This affects any WordPress theme with `no-sidebar`, `sidebar-none`, `hide-sidebar`, `sidebar-collapsed`, etc. — common WordPress class patterns.

## What Changes

Replace the substring regex matching with **exact CSS class token matching**. HTML class attributes are space-separated tokens. `class="home no-sidebar wp-theme"` has tokens `["home", "no-sidebar", "wp-theme"]`. None of these equals `"sidebar"` — the match should fail.

Additionally, never decompose `<html>` or `<body>` elements regardless of class — removing structural root elements is always wrong.

## Capabilities

### New Capabilities
_(None — bug fix on existing scraping logic.)_

### Modified Capabilities
_(None.)_

## Impact

- **Modified**: `backend/src/data_strategies/web_scraper_strategy.py` — class-based element removal uses token-level matching instead of substring regex
- **Tests**: add test case for `no-sidebar` body class (must not strip content); verify existing scraping behavior unchanged
- **No frontend or infrastructure changes**
- **Unblocks**: blinkeye.com and any other site with compound class names containing clutter keywords as substrings
