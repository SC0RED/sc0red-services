## ADDED Requirements

### Requirement: Context-aware link extraction
The web scraper SHALL return contextual text for each link: the nearest ancestor heading text, parent card/article text, `aria-label`, `title` attribute, and `img alt` text. This context SHALL be available to the heuristic filter for company name extraction when `<a>` text is generic CTA.

#### Scenario: LEARN MORE link with heading context
- **WHEN** a link has text "LEARN MORE" and its parent `<article>` contains `<h3>Access Healthcare</h3>`
- **THEN** the scraper returns `{text: "LEARN MORE", href: "...", context_name: "Access Healthcare"}`

#### Scenario: Image-only link with alt text
- **WHEN** a link contains an `<img alt="Acme Corp">` and no text
- **THEN** the scraper returns `{text: "", href: "...", context_name: "Acme Corp"}`

### Requirement: AI page extraction runs in parallel with heuristics
The AI extraction path SHALL receive the scraped page text and link list, and return a structured list of portfolio companies with names and URLs. It SHALL run in parallel with the heuristic path using FutureManager.

#### Scenario: AI extracts companies from page text
- **WHEN** the scraped page contains text about portfolio companies
- **THEN** the AI returns a JSON list of `{name, url}` objects extracted from the page content

#### Scenario: Non-PE firm page
- **WHEN** the scraped page is from a professional services firm (not PE)
- **THEN** the AI returns an empty list and a message indicating this is not a PE firm

### Requirement: AI extraction prompt externalized
The AI extraction prompt SHALL be stored in `src/pipeline/prompts/templates/extract_portfolio_companies.md` following the existing prompt externalization pattern.

#### Scenario: Prompt loaded from file
- **WHEN** the AI extraction runs
- **THEN** the prompt is loaded from the external template file, not inline in Python

### Requirement: Heuristic path uses context for CTA links
When the heuristic filter encounters a link with generic CTA text (matching `_GENERIC_CTA_PATTERNS`), it SHALL check `context_name` for a valid company name instead of dropping the link.

#### Scenario: CTA link with context name passes filter
- **WHEN** a link has text "Learn More" but `context_name` is "Stripe Inc"
- **THEN** the heuristic filter uses "Stripe Inc" as the company name and includes the link

#### Scenario: CTA link without any context name
- **WHEN** a link has text "Learn More" and no `context_name`
- **THEN** the heuristic filter drops the link (same as current behavior)
