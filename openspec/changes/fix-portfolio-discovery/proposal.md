## Why

Customer-reported bug: portfolio discovery returns 0 companies for PE firms with real portfolios (perotjain.com, bdo.com). Root cause for perotjain.com: the page renders fine (79KB HTML, 100 links, company URLs present) but every portfolio company link has "LEARN MORE" as its text — which the `_GENERIC_CTA_PATTERNS` filter drops. Company names exist in sibling `<h3>` elements, not in the `<a>` text. For bdo.com: not a PE firm (no portfolio pages exist at expected paths) — but the user gets no feedback explaining why.

This is the #1 conversion-blocking bug: a prospective customer tries the product, enters their firm, sees 0 results, and leaves.

## What Changes

- **Parallel discovery architecture**: Two independent paths run simultaneously on the scraped page:
  1. **Heuristic path (improved)**: Context-aware link extraction that reads company names from parent/sibling elements when `<a>` text is generic CTA
  2. **AI page analysis path**: Sends scraped page text + links to LLM to extract portfolio companies

- **Result merging strategy**:
  - Intersection (both paths agree) → auto-included, high confidence
  - Remainder (one path only) → validated by AI with yes/no: "Is this a portfolio company?"

- **Diagnostic logging**: Log filter decisions at INFO level so we can see why links are rejected

- **Better error feedback**: When 0 companies found, return context ("page has no portfolio section" vs "found links but couldn't identify companies" vs "site appears to be a professional services firm, not a PE firm")

## Capabilities

### New Capabilities
- `ai-page-extraction`: LLM-based portfolio company extraction from scraped page text, running in parallel with heuristic filters
- `discovery-merging`: Confidence-based merging of heuristic and AI results with AI validation for uncertain candidates

### Modified Capabilities

## Impact

- **Modified**: `src/data_strategies/portfolio_discovery_strategy.py` — major rewrite of discovery logic
- **Modified**: `src/data_strategies/web_scraper_strategy.py` — add context extraction for links (parent/sibling text)
- **New**: AI prompt for page extraction in `src/pipeline/prompts/`
- **New**: AI prompt for company validation in `src/pipeline/prompts/`
- **No frontend changes**: discovery results feed into existing confirm flow
- **No infrastructure changes**: uses existing AI pipeline infrastructure
