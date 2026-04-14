## 1. Scraper enhancement

- [x] 1.1 Add context extraction to `scrape_url()` — heading, img alt, aria-label, title
- [x] 1.2 Return `context_name` field alongside `text` and `href` in link dicts

- [ ] 1.3 Unit tests for context extraction (heading in parent article, img alt, aria-label)

## 2. Heuristic path improvement

- [x] 2.1 When link text matches `_GENERIC_CTA_PATTERNS`, check `context_name` before dropping
- [x] 2.2 Use `context_name` as the company name if valid (passes length + prefix filters)
- [x] 2.3 Add diagnostic logging: log each filter rejection with filter name and link details at INFO
- [ ] 2.4 Unit tests for CTA-with-context passing, CTA-without-context dropping

## 3. AI page extraction path

- [ ] 3.1 Create prompt template `src/pipeline/prompts/templates/extract_portfolio_companies.md`
- [ ] 3.2 Implement AI extraction function: takes page text + links, calls LLM, returns `[{name, url}]`
- [ ] 3.3 Use `run_structured_ai_call` following mandatory pipeline pattern
- [ ] 3.4 Create JSON schema for extraction response in `src/pipeline/prompts/schemas/`
- [ ] 3.5 Unit tests with mocked AI response

## 4. AI validation prompt

- [ ] 4.1 Create prompt template `src/pipeline/prompts/templates/validate_portfolio_company.md`
- [ ] 4.2 Implement validation function: takes company name + URL + firm name, returns yes/no
- [ ] 4.3 Create JSON schema for validation response
- [ ] 4.4 Unit tests with mocked AI response

## 5. Parallel execution and merging

- [ ] 5.1 Refactor `PortfolioDiscoveryStrategy.execute()` to run heuristic + AI in parallel via FutureManager
- [ ] 5.2 Implement URL domain normalization for matching (strip www., trailing slash, compare netloc)
- [ ] 5.3 Implement merge logic: intersection auto-include, remainder → AI validation
- [ ] 5.4 Run AI validation on remainder candidates in parallel (batch)
- [ ] 5.5 Return merged final list with diagnostic message
- [ ] 5.6 Unit tests for merging (intersection, remainder validation, URL normalization)

## 6. Error feedback

- [ ] 6.1 Detect non-PE-firm pages (no portfolio paths, AI says "not PE") and return descriptive message
- [ ] 6.2 Detect "found links but all filtered" and return descriptive message
- [ ] 6.3 Return diagnostic message in discovery result `{"companies": [...], "message": "..."}`

## 7. Integration testing

- [ ] 7.1 Test with perotjain.com URL — verify > 0 companies discovered
- [ ] 7.2 Test with a known working PE firm — verify same or better results
- [ ] 7.3 Test with bdo.com — verify descriptive error message returned

## 8. Verify

- [ ] 8.1 All lint checks pass (ruff, format, naming, abbreviations, bandit)
- [ ] 8.2 All tests pass with ≥95% coverage
- [ ] 8.3 File size check — all files under 400 lines
- [ ] 8.4 Architecture review + audit
