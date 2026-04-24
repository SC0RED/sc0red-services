## Context

Portfolio discovery scrapes PE firm websites across 6 URL paths (`/portfolio`, `/companies`, etc.), extracts `<a>` tags, and filters them through heuristics to find portfolio company links. The current heuristics fail when:

1. Link text is generic CTA ("LEARN MORE", "Visit Website") — filtered by `_GENERIC_CTA_PATTERNS`
2. Company names are in parent/sibling elements, not in the `<a>` tag text
3. Non-PE firms (like BDO.com) have no portfolio pages — user gets silent 0 results

The fix runs two parallel discovery paths on the same scraped page data, then merges results with confidence scoring.

## Discovery Architecture

```
scrape_url(firm_url) → page_text + links
          │
          ├─────────────────────────────────┐
          ▼                                 ▼
  Heuristic Path                     AI Page Analysis
  ─────────────                      ────────────────
  1. Extract links with context      1. Send page text + link
     (parent heading, card title)       list to LLM
  2. For CTA links, look up          2. LLM returns structured
     company name from context          list: [{name, url}]
  3. Apply relaxed filters           3. Includes companies from
  4. Return candidates A                any page structure
                                     4. Return candidates B
          │                                 │
          └──────────┬──────────────────────┘
                     ▼
              Merge Results
              ─────────────
              Intersection (A ∩ B):
                → AUTO-INCLUDE (both paths agree)

              Remainder (A △ B):
                → AI VALIDATION: "Is {name} at {url}
                  a portfolio company of {firm}? yes/no"
                → Include if yes
                     │
                     ▼
              Final company list
```

## Goals / Non-Goals

**Goals:**
- Fix 0-company discovery for perotjain.com and similar CTA-heavy sites
- Parallel heuristic + AI paths for higher accuracy
- Confidence-based merging (intersection = high, single-source = validated)
- Diagnostic logging showing why companies were found/rejected
- Meaningful feedback when 0 companies found

**Non-Goals:**
- JavaScript rendering (perotjain.com renders statically — this is not needed)
- Changing the scraping library (httpx + BeautifulSoup is sufficient)
- Changing the downstream pipeline (validate, confirm, analyze)

## Decisions

### 1. Context-aware link extraction in scraper

**Decision: Enhance `scrape_url()` to return contextual text for each link — the parent element's text, nearby headings, and card title.**

When the link text is "LEARN MORE", the scraper looks for the company name in:
1. The closest ancestor `<article>`, `<div>`, `<li>` that contains a heading (`<h2>`, `<h3>`, `<h4>`)
2. The `aria-label` attribute on the link
3. The `title` attribute on the link
4. The `alt` text of an `<img>` inside the link

This context is returned alongside the link text so the heuristic filter can use the company name even when the `<a>` text is generic.

### 2. AI extraction uses scraped page text (not training data)

**Decision: The AI path receives the actual scraped page text and link list — it does NOT rely on LLM training knowledge about the firm.**

This ensures:
- Current portfolio (not stale training data)
- The firm's own website is the source of truth
- AI interprets page structure, not recalls from memory

### 3. Parallel execution via FutureManager

**Decision: Use the existing `FutureManager` pattern from the pipeline for parallel execution of heuristic + AI paths.**

Both paths receive the same scraped page data. FutureManager handles thread pooling. This follows the mandatory codebase pattern for parallel AI calls.

### 4. AI prompts externalized to files

**Decision: All AI prompts in `src/pipeline/prompts/templates/` following existing pattern.**

Two new prompts:
- `extract_portfolio_companies.md` — given page text, extract company names + URLs
- `validate_portfolio_company.md` — given company name + URL + firm name, is this a portfolio company? yes/no

### 5. Merge by URL domain matching

**Decision: Match candidates between heuristic and AI paths by normalized URL domain (not by company name).**

Company names may differ slightly ("Access Healthcare" vs "Access Healthcare Inc"). URL domains are more stable. Normalize by stripping www., trailing slashes, and comparing netloc.

### 6. Diagnostic logging at INFO level

**Decision: Log key filter decisions at INFO (not DEBUG) so they're visible in CloudWatch without enabling debug mode.**

Log: total links found, links rejected by each filter (with reason), candidates from each path, intersection count, validation results.

## Risks / Trade-offs

- **AI cost**: Running AI extraction on every portfolio discovery adds ~$0.01-0.05 per scan. Acceptable given this is a one-time discovery step per scan.
- **AI latency**: Adds ~2-3s, but runs in parallel with heuristic path, so total time is max(heuristic, AI) not sum.
- **AI extraction quality**: LLM may miss companies or hallucinate from page text. Mitigated by intersection with heuristic path + validation step.
- **Over-inclusion risk**: Relaxed heuristic filters may include non-portfolio links. Mitigated by AI validation on uncertain candidates.
