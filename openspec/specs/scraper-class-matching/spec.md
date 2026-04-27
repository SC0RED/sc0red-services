# scraper-class-matching Specification

## Purpose
TBD - created by archiving change fix-scraper-class-matching. Update Purpose after archive.
## Requirements
### Requirement: Clutter removal uses exact CSS class token matching

The scraper's clutter-removal step SHALL match against individual CSS class tokens, not substrings of the class attribute string.

#### Scenario: Element with exact clutter class is removed

- **WHEN** scraping a page with `<div class="sidebar">content</div>`
- **THEN** the div is removed from the DOM before text extraction

#### Scenario: Element with compound class containing clutter keyword is preserved

- **WHEN** scraping a page with `<body class="home no-sidebar wp-theme">content</body>`
- **THEN** the body is NOT removed — `"no-sidebar"` is a single token that does not equal `"sidebar"`

#### Scenario: html and body elements are never decomposed

- **WHEN** scraping a page where `<body>` has a class exactly matching a clutter pattern (e.g., `class="sidebar"`)
- **THEN** the body is still NOT removed — structural root elements are always preserved

