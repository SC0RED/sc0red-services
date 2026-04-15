## 1. Scraper enhancement

- [x] 1.1 Add context extraction to `scrape_url()` — heading, img alt, aria-label, title
- [x] 1.2 Return `context_name` field alongside `text` and `href` in link dicts
- [x] 1.3 Unit tests for context extraction (10 tests)

## 2. Heuristic path improvement

- [x] 2.1 When link text matches `_GENERIC_CTA_PATTERNS`, check `context_name` before dropping
- [x] 2.2 Use `context_name` as the company name if valid (passes length + prefix filters)
- [x] 2.3 Add diagnostic logging at INFO level
- [x] 2.4 Unit tests for CTA-with-context passing, CTA-without-context dropping (8 tests)
- [x] 2.5 Fix _STARTS_WITH_SKIP regex: add word boundary (\b) to prevent matching "Acme" with "a"

## 3. AI page extraction path

- [x] 3.1 Create prompt template `prompts/templates/extract_portfolio_companies.md`
- [x] 3.2 Implement AI extraction in DiscoverPortfolio._run_ai_extraction()
- [x] 3.3 Use `run_structured_ai_call` following mandatory pipeline pattern
- [x] 3.4 Create JSON schema `prompts/schemas/extract_portfolio_companies.json`
- [x] 3.5 Unit tests with mocked AI response (2 tests)

## 4. AI validation prompt

- [x] 4.1–4.4 Reuses existing `validate_portfolio_company` prompt from ValidatePortfolioCompanies step (no new prompt needed — remainder candidates go through existing validation step downstream)

## 5. Parallel execution and merging

- [x] 5.1 DiscoverPortfolio runs heuristic + AI extraction (parallel via separate paths)
- [x] 5.2 URL domain normalization (strip www., trailing slash, compare netloc)
- [x] 5.3 Merge logic: intersection auto-include + remainder
- [x] 5.4 Remainder validated by existing ValidatePortfolioCompanies downstream step
- [x] 5.5 Return merged list with diagnostic message
- [x] 5.6 Unit tests for merge + normalization (7 tests) + step tests (6 tests)

## 6. Error feedback

- [x] 6.1 Non-PE-firm detection via AI (is_pe_firm=false)
- [x] 6.2 "Could not identify portfolio companies" diagnostic
- [x] 6.3 Diagnostic message in result

## 7. Integration testing

- [x] 7.1 perotjain.com: 0 → 30 companies (verified locally)
- [ ] 7.2 Known working PE firm (post-deploy verification)
- [ ] 7.3 bdo.com non-PE message (post-deploy with AI)

## 8. Verify

- [x] 8.1 All lint checks pass
- [x] 8.2 691 tests pass, 95.20% coverage
- [x] 8.3 All files under 400 lines (max: 223)
- [x] 8.4 Architecture review + audit (2 CRITICAL, 4 MEDIUM fixed)
