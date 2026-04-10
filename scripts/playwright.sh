#!/usr/bin/env bash
#
# Unified Playwright E2E test runner.
#
# Usage:
#   ./scripts/playwright.sh --mode=local                          # Full local E2E (docker lifecycle managed)
#   ./scripts/playwright.sh --mode=local --headed                 # Watch tests in Chrome
#   ./scripts/playwright.sh --mode=local --ui                     # Interactive Playwright debugger
#   ./scripts/playwright.sh --mode=local --visual                 # Run + visual regression comparison
#   ./scripts/playwright.sh --mode=local --visual-update          # Update visual baselines
#   ./scripts/playwright.sh --mode=smoke --url=https://dev.app    # Smoke tests against deployed dev
#   ./scripts/playwright.sh --mode=deployed --url=https://test.app # Full E2E against deployed testing
#
set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ── Defaults ──────────────────────────────────────────────────────
MODE=""
URL=""
HEADED=""
VISUAL=""
VISUAL_UPDATE=""
CLEANUP=""
USER_POOL_ID=""
TABLE=""
REGION="us-east-1"
PLAYWRIGHT_EXTRA_ARGS=()

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# ── Parse arguments ───────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --mode=*)    MODE="${arg#*=}" ;;
        --url=*)     URL="${arg#*=}" ;;
        --headed)    HEADED="--headed" ;;
        --ui)        HEADED="--ui" ;;
        --debug)     HEADED="--debug" ;;
        --visual)    VISUAL="true" ;;
        --visual-update) VISUAL="true"; VISUAL_UPDATE="true" ;;
        --cleanup)   CLEANUP="true" ;;
        --user-pool-id=*) USER_POOL_ID="${arg#*=}" ;;
        --table=*)   TABLE="${arg#*=}" ;;
        --region=*)  REGION="${arg#*=}" ;;
        *)           echo -e "${RED}Unknown argument: $arg${NC}"; exit 1 ;;
    esac
done

# ── Validate mode ─────────────────────────────────────────────────
if [ -z "$MODE" ]; then
    echo -e "${CYAN}Janus Playwright E2E Test Runner${NC}"
    echo ""
    echo "Usage: ./scripts/playwright.sh --mode=<mode> [options]"
    echo ""
    echo -e "${YELLOW}Modes (required):${NC}"
    echo "  --mode=local      Run against local docker-compose stack (mock AI, mock auth)"
    echo "  --mode=smoke      Run against deployed dev environment (real Cognito)"
    echo "  --mode=deployed   Run against deployed testing environment (real Cognito + real AI)"
    echo ""
    echo -e "${YELLOW}Options:${NC}"
    echo "  --url=<url>            Frontend URL (required for smoke/deployed modes)"
    echo "  --headed               Run with visible Chrome browser"
    echo "  --ui                   Launch Playwright interactive UI debugger"
    echo "  --debug                Step through tests with Playwright inspector"
    echo "  --visual               Run visual regression (screenshot comparison)"
    echo "  --visual-update        Update visual regression baselines"
    echo ""
    echo -e "${YELLOW}Cleanup (smoke/deployed modes):${NC}"
    echo "  --cleanup              Run cleanup after tests (requires AWS credentials)"
    echo "  --user-pool-id=<id>    Cognito User Pool ID (auto-discovered if omitted)"
    echo "  --table=<name>         DynamoDB table name (auto-discovered if omitted)"
    echo "  --region=<region>      AWS region (default: us-east-1)"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo "  ./scripts/playwright.sh --mode=local"
    echo "  ./scripts/playwright.sh --mode=local --headed"
    echo "  ./scripts/playwright.sh --mode=local --visual-update"
    echo "  ./scripts/playwright.sh --mode=smoke --url=https://dev.example.com"
    echo "  ./scripts/playwright.sh --mode=smoke --url=https://dev.example.com --cleanup"
    exit 1
fi

if [[ "$MODE" != "local" && "$MODE" != "smoke" && "$MODE" != "deployed" ]]; then
    echo -e "${RED}Invalid mode: $MODE${NC}"
    echo "Valid modes: local, smoke, deployed"
    exit 1
fi

if [[ "$MODE" != "local" && -z "$URL" ]]; then
    echo -e "${RED}--url is required for --mode=$MODE${NC}"
    echo "Example: ./scripts/playwright.sh --mode=$MODE --url=https://your-app.amplifyapp.com"
    exit 1
fi

# ── Build Playwright project list ─────────────────────────────────
PROJECTS=()

case "$MODE" in
    local)
        PROJECTS+=(--project=local --project=local-post-scan --project=local-expiry)
        if [ "$VISUAL" = "true" ]; then
            PROJECTS+=(--project=local-visual --project=local-visual-post-scan)
        fi
        ;;
    smoke)
        PROJECTS+=(--project=smoke)
        if [ "$VISUAL" = "true" ]; then
            PROJECTS+=(--project=smoke-visual)
        fi
        ;;
    deployed)
        PROJECTS+=(--project=deployed --project=deployed-post-scan --project=deployed-cleanup)
        ;;
esac

if [ "$VISUAL_UPDATE" = "true" ]; then
    PLAYWRIGHT_EXTRA_ARGS+=(--update-snapshots)
fi

if [ -n "$HEADED" ]; then
    PLAYWRIGHT_EXTRA_ARGS+=("$HEADED")
fi

# ── Local mode: cleanup handler ───────────────────────────────────
NEXTJS_PID=""
DOCKER_STARTED=""

cleanup_local() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    if [ -n "$NEXTJS_PID" ]; then
        kill "$NEXTJS_PID" 2>/dev/null || true
        # Also kill any orphaned Next.js processes on port 3000
        lsof -ti:3000 2>/dev/null | xargs kill 2>/dev/null || true
    fi
    if [ "$DOCKER_STARTED" = "true" ]; then
        echo -e "${YELLOW}Tearing down docker-compose...${NC}"
        docker compose -f "$PROJECT_ROOT/docker-compose.e2e.yml" down -v 2>/dev/null || true
    fi
}

# ── Local mode: full lifecycle ────────────────────────────────────
run_local() {
    trap cleanup_local EXIT INT TERM

    # 1. Check Docker is running
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}Docker is not running. Please start Docker Desktop.${NC}"
        exit 1
    fi

    # 2. Start docker-compose
    echo -e "${CYAN}Starting E2E docker stack...${NC}"
    GH_TOKEN="${GH_TOKEN:-$(gh auth token 2>/dev/null || echo '')}"
    export GH_TOKEN
    docker compose -f "$PROJECT_ROOT/docker-compose.e2e.yml" up --build -d 2>&1 | tail -5
    DOCKER_STARTED="true"

    # 3. Wait for backend health
    echo -e "${YELLOW}Waiting for backend...${NC}"
    for i in $(seq 1 30); do
        if curl -sf http://localhost:8001/api/health > /dev/null 2>&1; then
            echo -e "${GREEN}Backend ready${NC}"
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo -e "${RED}Backend did not start in time${NC}"
            docker compose -f "$PROJECT_ROOT/docker-compose.e2e.yml" logs backend
            exit 1
        fi
        sleep 2
    done

    # 4. Setup infrastructure (DynamoDB + SQS + S3)
    echo -e "${YELLOW}Setting up infrastructure...${NC}"
    python3 "$PROJECT_ROOT/scripts/setup_dynamodb.py" --table janus-e2e --endpoint http://localhost:4566
    python3 -c "
import boto3
sqs = boto3.client('sqs', endpoint_url='http://localhost:4566', region_name='us-east-1',
    aws_access_key_id='local', aws_secret_access_key='local')
sqs.create_queue(QueueName='janus-analysis-e2e')
s3 = boto3.client('s3', endpoint_url='http://localhost:4566', region_name='us-east-1',
    aws_access_key_id='local', aws_secret_access_key='local')
try:
    s3.create_bucket(Bucket='janus-documents-e2e')
except Exception:
    pass
print('Infrastructure ready')
"

    # 5. Start Next.js dev server
    echo -e "${YELLOW}Starting Next.js dev server...${NC}"
    cd "$FRONTEND_DIR"
    NEXTAUTH_SECRET=dev-secret-minimum-32-characters-long \
    NEXTAUTH_URL=http://localhost:3000 \
    BACKEND_URL=http://localhost:8001 \
    NEXT_PUBLIC_COGNITO_USER_POOL_ID=us-east-1_TESTPOOL1 \
    NEXT_PUBLIC_COGNITO_CLIENT_ID=test-client-id-placeholder \
    npm run dev > /tmp/janus-nextjs-e2e.log 2>&1 &
    NEXTJS_PID=$!

    for i in $(seq 1 30); do
        if curl -sf http://localhost:3000 > /dev/null 2>&1; then
            echo -e "${GREEN}Next.js ready${NC}"
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo -e "${RED}Next.js did not start in time${NC}"
            tail -20 /tmp/janus-nextjs-e2e.log
            exit 1
        fi
        sleep 2
    done

    # 6. Run Playwright
    echo -e "\n${CYAN}Running Playwright tests (mode=$MODE)...${NC}"
    cd "$FRONTEND_DIR"
    BACKEND_URL=http://localhost:8001 \
    NEXTAUTH_SECRET=dev-secret-minimum-32-characters-long \
    npx playwright test "${PROJECTS[@]}" ${PLAYWRIGHT_EXTRA_ARGS[@]+"${PLAYWRIGHT_EXTRA_ARGS[@]}"}
}

# ── Smoke / Deployed mode ────────────────────────────────────────
run_remote() {
    local test_exit_code=0

    echo -e "${CYAN}Running Playwright tests (mode=$MODE, url=$URL)...${NC}"
    cd "$FRONTEND_DIR"
    PLAYWRIGHT_BASE_URL="$URL" \
    npx playwright test "${PROJECTS[@]}" ${PLAYWRIGHT_EXTRA_ARGS[@]+"${PLAYWRIGHT_EXTRA_ARGS[@]}"} || test_exit_code=$?

    # Cleanup: delete e2e-* test users from Cognito + DynamoDB (runs even if tests fail)
    if [ "$CLEANUP" = "true" ]; then
        echo -e "\n${YELLOW}Running cleanup (Cognito + DynamoDB)...${NC}"
        local cleanup_args=(--region "$REGION")
        [ -n "$USER_POOL_ID" ] && cleanup_args+=(--user-pool-id "$USER_POOL_ID")
        [ -n "$TABLE" ] && cleanup_args+=(--table "$TABLE")
        python3 "$PROJECT_ROOT/scripts/e2e-cleanup.py" "${cleanup_args[@]}" || echo -e "${RED}Cleanup failed (non-fatal)${NC}"
    elif [ "$MODE" != "local" ]; then
        echo -e "\n${YELLOW}Skipping cleanup — pass --cleanup to enable (requires AWS credentials)${NC}"
    fi

    return $test_exit_code
}

# ── Execute ───────────────────────────────────────────────────────
echo -e "${CYAN}Janus E2E Tests — mode=$MODE${NC}"
echo ""

case "$MODE" in
    local)    run_local ;;
    smoke)    run_remote ;;
    deployed) run_remote ;;
esac
