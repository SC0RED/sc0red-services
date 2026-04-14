## 1. Cleanup

- [x] 1.1 Delete `src/mcp/api_client.py`
- [x] 1.2 Remove `INTERNAL_SIGNING_KEY` from CDK environment variables in `mcp_construct.py` (if present)
- [x] 1.3 Remove `api_client.py` from `pyproject.toml` coverage omit (if present)

## 2. Storage initialization

- [x] 2.1 Initialize `DynamoDBStorageProvider` in `mcp_handler.py`
- [x] 2.2 Create repositories from provider (assessment, company, scan, user, invitation)
- [x] 2.3 Update `register_read_tools(mcp, storage)` signature to accept storage
- [x] 2.4 Update `register_search_tools(mcp, storage)` signature to accept storage

## 3. Rewrite read tools (tools_read.py)

- [x] 3.1 `get_dashboard` — company_repo.find_by_org + scan_repo.find_recent_by_org
- [x] 3.2 `list_analyses` — company_repo.find_by_org, filter analyzed
- [x] 3.3 `get_analysis` — company_repo.get_by_id + assessment data (mirrors handle_get_analysis)
- [x] 3.4 `get_risk_breakdown` — company_repo.get_by_id + assessment_repo.get_risk_scores
- [x] 3.5 `get_opportunities` — company_repo.get_by_id + assessment_repo.get_opportunities
- [x] 3.6 `get_ebitda_tree` — company_repo.get_by_id + assessment_repo.get_ebitda_tree
- [x] 3.7 `get_value_chain` — company_repo.get_by_id + assessment_repo.get_value_chain
- [x] 3.8 `get_scan` — scan_repo.get_by_id + scan_companies + company_repo.get_by_ids
- [x] 3.9 `list_team_members` — user_repo.find_by_org + invitation_repo.find_by_org
- [x] 3.10 `list_documents` — company_repo.get_by_id + assessment_repo.get_documents

## 4. Rewrite search tools (tools_search.py)

- [x] 4.1 `search_analyses` — company_repo.find_by_org, filter in Python
- [x] 4.2 `compare_analyses` — company_repo.get_by_id for each + assessment data

## 5. Rewrite tests

- [x] 5.1 Create repository mock fixtures (_make_storage, _setup_assessment)
- [x] 5.2 Rewrite all tool tests to use repository mocks (30 tests)
- [x] 5.3 Add auth_context setup fixture to all tests

## 6. Verify

- [x] 6.1 Ruff lint — clean
- [x] 6.2 Ruff format — clean
- [x] 6.3 Naming + abbreviation checks — clean
- [x] 6.4 650 tests pass, 95.05% coverage
- [x] 6.5 All files under 400 lines (max: 357)
- [ ] 6.6 Architecture review + audit
