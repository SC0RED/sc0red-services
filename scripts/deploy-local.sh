#!/usr/bin/env bash
#
# Deploy the Janus CDK stack to LocalStack for local testing.
#
# Usage: ./scripts/deploy-local.sh
#
# Prerequisites:
#   - Docker running
#   - GH_TOKEN set (or available via: export GH_TOKEN=$(gh auth token))
#   - npm (for aws-cdk + aws-cdk-local)
#   - uv (for CDK Python deps)
#
set -euo pipefail

LOCALSTACK_URL="http://localhost:4566"
CDK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../infrastructure" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

log() { echo -e "${YELLOW}▶ $*${NC}"; }
ok()  { echo -e "${GREEN}✓ $*${NC}"; }
err() { echo -e "${RED}✗ $*${NC}" >&2; exit 1; }

# ── Prerequisites ──────────────────────────────────────────────────────────────

log "Checking prerequisites..."

command -v docker >/dev/null 2>&1 || err "Docker not found"
command -v npm >/dev/null 2>&1    || err "npm not found"
command -v uv >/dev/null 2>&1     || err "uv not found"

if [ -z "${GH_TOKEN:-}" ]; then
    if command -v gh >/dev/null 2>&1; then
        export GH_TOKEN
        GH_TOKEN=$(gh auth token)
        ok "GH_TOKEN obtained from gh CLI"
    else
        err "GH_TOKEN not set and gh CLI not available"
    fi
fi

# ── CDK CLI ────────────────────────────────────────────────────────────────────

if ! command -v cdklocal >/dev/null 2>&1; then
    log "Installing aws-cdk and aws-cdk-local..."
    npm install -g aws-cdk aws-cdk-local --silent
fi
ok "cdklocal ready: $(cdklocal --version)"

# ── CDK Python deps ────────────────────────────────────────────────────────────

log "Installing CDK Python dependencies..."
cd "$CDK_DIR"
uv sync --quiet
ok "CDK Python deps ready"

# ── LocalStack ─────────────────────────────────────────────────────────────────

if ! docker ps --format '{{.Names}}' | grep -q "janus-localstack"; then
    log "Starting LocalStack..."
    cd "$CDK_DIR/.."
    docker compose --profile localstack up localstack -d
    cd "$CDK_DIR"
fi

log "Waiting for LocalStack to be ready..."
for i in $(seq 1 30); do
    if curl -sf "${LOCALSTACK_URL}/_localstack/health" 2>/dev/null | python3 -c \
        "import sys,json; s=json.load(sys.stdin).get('services',{}); exit(0 if s.get('lambda')=='available' or s.get('lambda')=='running' else 1)" 2>/dev/null; then
        ok "LocalStack is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then err "LocalStack did not become ready in time"; fi
    sleep 2
done

# ── CDK Bootstrap + Deploy ─────────────────────────────────────────────────────

export AWS_ACCESS_KEY_ID=local
export AWS_SECRET_ACCESS_KEY=local
export AWS_DEFAULT_REGION=us-east-1
export CDK_ENVIRONMENT=development

log "Bootstrapping CDK..."
# LocalStack default account
cdklocal bootstrap aws://000000000000/us-east-1 --quiet 2>&1 | grep -v "^$" || true

log "Deploying Janus-development to LocalStack..."
DEPLOY_OUTPUT=$(cdklocal deploy Janus-development --require-approval never --outputs-file /tmp/janus-outputs.json 2>&1)
echo "$DEPLOY_OUTPUT"

# ── Extract URL ────────────────────────────────────────────────────────────────

if [ -f /tmp/janus-outputs.json ]; then
    API_URL=$(python3 -c "
import json
with open('/tmp/janus-outputs.json') as f:
    outputs = json.load(f)
stack = outputs.get('Janus-development', {})
for key, val in stack.items():
    if 'ApiUrl' in key:
        print(val)
        break
" 2>/dev/null || echo "")
fi

if [ -z "${API_URL:-}" ]; then
    # Fallback: extract from deploy output
    API_URL=$(echo "$DEPLOY_OUTPUT" | grep -oP 'https?://[^\s]+execute-api[^\s]+' | head -1 || true)
fi

echo ""
echo "════════════════════════════════════════"
if [ -n "${API_URL:-}" ]; then
    ok "Deployment complete!"
    echo ""
    echo "  Backend API: ${API_URL}"
    echo "  Health:      ${API_URL}api/health"
    echo ""
    echo "Test it:"
    echo "  curl ${API_URL}api/health"
else
    ok "Deployment complete! (check above for Janus-development.ApiUrl)"
fi
echo "════════════════════════════════════════"
