## MODIFIED Requirements

### Requirement: AI extraction receives enough page content to cover large portfolios

The AI-based extraction path SHALL send enough scraped content and enough link entries to the LLM that a portfolio page with 70+ companies is not truncated mid-list. Critically, the content SHALL be drawn from the **raw HTML — including `<script>` contents** — not only the cleaned visible-body text, because many firm sites (e.g. Next.js-style sites) server-render an empty body skeleton and embed the portfolio companies as a JSON hydration island inside a `<script>` tag. The extractor SHALL be given the data-bearing portion of that raw HTML (the visible body text plus the data-bearing `<script>` JSON, selected/truncated to a token budget), so embedded-JSON portfolios are extractable.

#### Scenario: Portfolio embedded as a script JSON island is extracted

- **WHEN** the firm page's visible `<body>` is a skeleton and its portfolio companies appear only inside a `<script>` JSON blob (e.g. `{"name":"Sophos","slug":"sophos",…}`)
- **THEN** the AI-extraction input includes that `<script>` JSON content (not just the empty body text)
- **AND** the extractor returns the embedded companies rather than zero

#### Scenario: Content budget accommodates large portfolios

- **WHEN** the discovery step invokes the AI extraction
- **THEN** the user prompt includes enough raw-HTML/script content and link text (within the configured budget) that a 70+ company page is not truncated mid-list

#### Scenario: Anchor-linked portfolios still extract

- **WHEN** a firm site exposes its companies as ordinary `<a>` links (no script-embedded JSON)
- **THEN** the heuristic link-filter path is unaffected and still discovers them, and the AI path also sees them via the raw HTML
