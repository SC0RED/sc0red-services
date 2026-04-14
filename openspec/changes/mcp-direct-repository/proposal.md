## Why

The MCP tools currently call the backend API via `api_client.py`, which mints HS256 tokens to authenticate. The backend only accepts RS256 Cognito JWTs — making every MCP tool call fail with 401 in deployed environments. This was a fundamentally wrong architecture: the MCP Lambda already has direct DynamoDB access (CDK `grant_read_write_data`), so there is no reason to route through HTTP.

## What Changes

- **Delete `api_client.py`** — the broken HTTP client with HS256 token minting
- **Delete `INTERNAL_SIGNING_KEY`** — remove from CDK environment variables and all references
- **Rewrite all 14 tool handlers** to call DynamoDB repositories directly instead of `call_backend()`
- **Initialize shared `DynamoDBStorageProvider`** in `mcp_handler.py` and pass to tool registration functions
- **Rewrite all 22 tool tests** to mock repository methods instead of mocking `call_backend`
- **Follow the exact same data assembly patterns** used by backend handlers (e.g., `handle_get_analysis`, `handle_dashboard`)

## Capabilities

### New Capabilities
- `mcp-repository-access`: Direct DynamoDB repository access pattern for MCP tools, using the same `DynamoDBStorageProvider` and repository classes as the backend

### Modified Capabilities

## Impact

- **Deleted**: `src/mcp/api_client.py`, `INTERNAL_SIGNING_KEY` env var
- **Rewritten**: `src/mcp/tools_read.py`, `src/mcp/tools_search.py`, all tool tests
- **Modified**: `src/mcp/mcp_handler.py` (initialize StorageProvider, pass to registration)
- **No backend handler changes**: repository layer is unchanged
- **No infrastructure changes**: MCP Lambda already has DynamoDB access
- **No new dependencies**: repositories already in the backend package
