## Context

MCP tools need to read Janus data (analyses, scans, companies, teams). The current approach routes through HTTP to the backend API, which requires auth token bridging that doesn't work. The MCP Lambda already has DynamoDB read/write access via CDK grants. The backend's repository layer (`DynamoDBStorageProvider` → individual repositories) provides clean read methods that the tools can call directly.

## Goals / Non-Goals

**Goals:**
- Every MCP tool reads data directly from DynamoDB via repositories
- Same data assembly logic as backend handlers (no divergence)
- Shared `DynamoDBStorageProvider` instance initialized once in mcp_handler.py
- All tools functional end-to-end (no more 401 errors)

**Non-Goals:**
- Write operations (scans, documents) — those stay in PR 3
- Changing the repository layer itself
- Changing backend handler code

## Decisions

### 1. Shared StorageProvider passed via registration function

**Decision: Initialize `DynamoDBStorageProvider` in `mcp_handler.py` and pass it to `register_read_tools(mcp, storage)` and `register_search_tools(mcp, storage)`.**

The registration functions create closures over the storage provider. Each tool accesses repositories via `storage.create_assessment_repository()` etc.

```python
# mcp_handler.py
storage = DynamoDBStorageProvider()
register_read_tools(mcp, storage)
register_search_tools(mcp, storage)
```

```python
# tools_read.py
def register_read_tools(mcp: FastMCP, storage: DynamoDBStorageProvider) -> None:
    assessment_repo = storage.create_assessment_repository()
    company_repo = storage.create_company_repository()
    scan_repo = storage.create_scan_repository()
    user_repo = storage.create_user_repository()

    @mcp.tool()
    async def get_analysis(analysis_id: str) -> str:
        company = company_repo.get_by_id(analysis_id)
        # ... same assembly as handle_get_analysis
```

### 2. Org scoping via auth_context

**Decision: Tools get the authenticated user's `org_id` from `get_authenticated_user()` (contextvars) and pass it to repository methods that filter by org.**

Repository methods like `company_repo.find_by_org(org_id)` and `scan_repo.find_recent_by_org(org_id)` already enforce org scoping. The MCP tool reads `org_id` from the authenticated user context.

### 3. Follow handler data assembly exactly

**Decision: Each tool's data assembly logic mirrors the corresponding backend handler exactly.**

For example, `get_analysis` tool follows the same pattern as `handle_get_analysis`:
1. `company_repo.get_by_id(analysis_id)` — the analysis_id IS the company_id in the data model
2. `assessment_repo.find_by_company(company_id)` — get assessments
3. `assessment_repo.get_risk_scores(assessment_id)` — risk dimensions
4. `assessment_repo.get_opportunities(assessment_id)` — opportunities
5. etc.

This ensures MCP tools return the same data as the web UI.

### 4. Synchronous repository calls in async tools

**Decision: Repository methods are synchronous (boto3). Call them directly in async tool handlers — boto3 handles its own connection pooling.**

FastMCP tool handlers are `async def` but boto3 DynamoDB calls are synchronous. This is fine for Lambda because there's no event loop contention — each Lambda invocation handles one request. The `async` signature is required by the MCP SDK but the actual I/O is synchronous boto3.

## Risks / Trade-offs

- **Data assembly duplication**: Tool handlers duplicate logic from backend handlers. → Mitigation: Follow the handler code exactly. If handlers change, tools must be updated too. Consider extracting shared data assembly into a service layer in a future PR.
- **Synchronous calls in async context**: boto3 is synchronous, called from async functions. → Mitigation: Fine for Lambda (single-request). Would need `asyncio.to_thread()` if ever running in a multi-request server.
