#!/bin/bash
# Lambda handler for the MCP server, run under the AWS Lambda Web Adapter (LWA).
#
# LWA (added as a layer in infrastructure/stacks/mcp_construct.py) sets
# AWS_LAMBDA_EXEC_WRAPPER=/opt/bootstrap, which makes the managed Python runtime
# execute this script instead of a Python handler. The script starts a real
# uvicorn ASGI server; LWA proxies the Lambda Function URL's HTTP requests to it
# on AWS_LWA_PORT. Because uvicorn runs the ASGI lifespan once at startup (not
# per invocation like Mangum did), StreamableHTTPSessionManager.run() is called
# exactly once — fixing the run-once 502 (design.md Decision 8).
set -euo pipefail
exec python -m uvicorn src.mcp.mcp_handler:app \
    --host 0.0.0.0 \
    --port "${AWS_LWA_PORT:-8080}"
