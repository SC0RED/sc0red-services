#!/usr/bin/env bash
#
# Deploy the Janus CDK stack to real AWS.
#
# Usage:
#   ./scripts/deploy-aws.sh [staging|production]
#
# Required environment variables:
#   NEXTAUTH_SECRET       — JWT secret for NextAuth session signing (≥32 chars)
#   AMPLIFY_GITHUB_TOKEN  — GitHub PAT for Amplify to clone the repo
#
# Optional environment variables:
#   ANTHROPIC_API_KEY  — Anthropic API key (defaults to sk-placeholder)
#   AWS_REGION         — Defaults to us-east-1
#
# Prerequisites:
#   - AWS credentials configured (env vars or aws configure)
#   - GH_TOKEN set or gh CLI authenticated (for bundling signalfield-core)
#   - npm (for aws-cdk)
#   - uv (for CDK Python deps)
#   - Docker (for Lambda bundling)
#
set -euo pipefail

ENVIRONMENT="${1:-staging}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CDK_DIR="$(cd "$SCRIPT_DIR/../infrastructure" && pwd)"

# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

# ── Validate environment ────────────────────────────────────────────────────────

if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "testing" && "$ENVIRONMENT" != "production" ]]; then
    err "Environment must be 'staging', 'testing', or 'production', got: $ENVIRONMENT"
fi

# ── Prerequisites ───────────────────────────────────────────────────────────────

log "Checking prerequisites..."

command -v docker >/dev/null 2>&1 || err "Docker not found — required for Lambda bundling"
command -v npm    >/dev/null 2>&1 || err "npm not found"
command -v uv     >/dev/null 2>&1 || err "uv not found"
command -v aws    >/dev/null 2>&1 || err "aws CLI not found"

# AWS credentials check
if ! aws sts get-caller-identity >/dev/null 2>&1; then
    err "AWS credentials not configured. Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY or run 'aws configure'."
fi
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGION="${AWS_REGION:-us-east-1}"
ok "AWS account: $ACCOUNT, region: $REGION"

# GH_TOKEN
require_gh_token

# NEXTAUTH_SECRET
if [ -z "${NEXTAUTH_SECRET:-}" ]; then
    err "NEXTAUTH_SECRET is required. Export it before running this script."
fi
ok "NEXTAUTH_SECRET set"

# ── CDK CLI ─────────────────────────────────────────────────────────────────────

if ! command -v cdk >/dev/null 2>&1; then
    log "Installing aws-cdk..."
    npm install -g aws-cdk --silent
fi
ok "cdk ready: $(cdk --version)"

# ── CDK Python deps ─────────────────────────────────────────────────────────────

log "Installing CDK Python dependencies..."
cd "$CDK_DIR"
uv sync --quiet
ok "CDK Python deps ready"

# ── CDK Bootstrap ───────────────────────────────────────────────────────────────

log "Bootstrapping CDK on aws://$ACCOUNT/$REGION (safe to re-run)..."
CDK_ENVIRONMENT="$ENVIRONMENT" \
    cdk bootstrap "aws://$ACCOUNT/$REGION" --quiet 2>&1 | grep -v "^$" || true
ok "CDK bootstrap complete"

# ── Deploy ──────────────────────────────────────────────────────────────────────

STACK_NAME="Janus-${ENVIRONMENT}"

log "Deploying $STACK_NAME to AWS..."
echo ""

CDK_ENVIRONMENT="$ENVIRONMENT" \
AWS_DEFAULT_REGION="$REGION" \
NEXTAUTH_SECRET="$NEXTAUTH_SECRET" \
AMPLIFY_GITHUB_TOKEN="${AMPLIFY_GITHUB_TOKEN:-}" \
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-sk-placeholder}" \
    cdk deploy "$STACK_NAME" \
        --require-approval never \
        --outputs-file /tmp/janus-aws-outputs.json \
        --context "environment=$ENVIRONMENT" \
        --context "account=$ACCOUNT" \
        --context "region=$REGION"

# ── Extract outputs ─────────────────────────────────────────────────────────────

API_URL=""
if [ -f /tmp/janus-aws-outputs.json ]; then
    API_URL=$(python3 -c "
import json
with open('/tmp/janus-aws-outputs.json') as f:
    outputs = json.load(f)
stack = outputs.get('$STACK_NAME', {})
for key, val in stack.items():
    if 'ApiUrl' in key:
        print(val)
        break
" 2>/dev/null || echo "")
fi

echo ""
echo "════════════════════════════════════════════════════════"
ok "Deployment complete! Stack: $STACK_NAME"
echo ""
if [ -n "$API_URL" ]; then
    echo "  Backend API URL : $API_URL"
    echo "  Health check    : ${API_URL}api/health"
    echo ""
    echo "Frontend is deployed via Amplify (auto-build on push)."
    echo "CORS is configured to the Amplify domain automatically."
else
    echo "  Check CloudFormation console for $STACK_NAME outputs (ApiUrl)"
fi
echo "════════════════════════════════════════════════════════"
