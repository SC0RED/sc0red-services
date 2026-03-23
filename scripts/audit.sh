#!/usr/bin/env bash
# Codebase audit — checks for common anti-patterns and quality drift.
# Run via: make audit
# Also runs in CI on every PR.
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

ERRORS=0

section() { echo -e "\n${YELLOW}▶ $*${NC}"; }
pass()    { echo -e "  ${GREEN}✓ $*${NC}"; }
fail()    { echo -e "  ${RED}✗ $*${NC}"; ERRORS=$((ERRORS + 1)); }
warn()    { echo -e "  ${YELLOW}⚠ $*${NC}"; }

# ── File size limits ─────────────────────────────────────────────────────────
section "File size limits (backend: 400 lines, frontend components: 360 lines)"

BACKEND_LIMIT=400
FRONTEND_LIMIT=360

while IFS= read -r line; do
    count=$(echo "$line" | awk '{print $1}')
    file=$(echo "$line" | awk '{print $2}')
    if [ "$count" -gt "$BACKEND_LIMIT" ]; then
        fail "$file: $count lines (limit: $BACKEND_LIMIT)"
    fi
done < <(find backend/src -name '*.py' -exec wc -l {} + 2>/dev/null | grep -v 'total$' | sort -rn)

if [ "$ERRORS" -eq 0 ]; then
    pass "All backend files under $BACKEND_LIMIT lines"
fi

FRONTEND_ERRORS_BEFORE=$ERRORS
while IFS= read -r line; do
    count=$(echo "$line" | awk '{print $1}')
    file=$(echo "$line" | awk '{print $2}')
    if [ "$count" -gt "$FRONTEND_LIMIT" ]; then
        fail "$file: $count lines (limit: $FRONTEND_LIMIT)"
    fi
done < <(find frontend/src/components -name '*.tsx' -exec wc -l {} + 2>/dev/null | grep -v 'total$' | sort -rn)

if [ "$ERRORS" -eq "$FRONTEND_ERRORS_BEFORE" ]; then
    pass "All frontend components under $FRONTEND_LIMIT lines"
fi

# ── Bare except Exception in workers ─────────────────────────────────────────
section "Exception handling in workers (no bare 'except Exception')"

# Check for bare 'except Exception' in pipeline execution paths (not the outer SQS record handler)
BARE_EXCEPT_COUNT=$(grep -c "except Exception:" backend/src/handlers/sqs_handler.py 2>/dev/null || echo "0")
SPECIFIC_EXCEPT_COUNT=$(grep -c "except (EngineError" backend/src/handlers/sqs_handler.py 2>/dev/null || echo "0")
# The outer handle() has one legitimate bare Exception catch for SQS batch failure reporting.
# Pipeline catches should use specific exceptions. If bare > 1, something is wrong.
if [ "$BARE_EXCEPT_COUNT" -gt 1 ]; then
    fail "sqs_handler.py has $BARE_EXCEPT_COUNT bare 'except Exception' — pipeline catches should use specific types"
elif [ "$SPECIFIC_EXCEPT_COUNT" -ge 1 ]; then
    pass "SQS handler pipeline catches use specific exception types (EngineError, etc.)"
else
    fail "SQS handler missing specific exception catches for pipeline errors"
fi

# ── DynamoDB pagination ──────────────────────────────────────────────────────
section "DynamoDB query pagination"

if grep -n "\.query(" backend/src/repositories/dynamodb/client.py | grep -qv "LastEvaluatedKey"; then
    # Check if pagination is implemented
    if grep -q "LastEvaluatedKey" backend/src/repositories/dynamodb/client.py; then
        pass "DynamoDB client.query() handles pagination via LastEvaluatedKey"
    else
        fail "DynamoDB client.query() does not handle pagination"
    fi
else
    pass "DynamoDB queries handle pagination"
fi

# ── N+1 reads (get_by_id in loops) ──────────────────────────────────────────
section "N+1 DynamoDB read patterns"

if grep -rn "for.*in.*:\s*$" backend/src/handlers/ 2>/dev/null | xargs -I{} grep -l "get_by_id" 2>/dev/null | head -1 | grep -q "."; then
    warn "Potential N+1 pattern found — verify batch reads are used"
else
    pass "No obvious N+1 get_by_id-in-loop patterns in handlers"
fi

# ── Infrastructure defaults ──────────────────────────────────────────────────
section "Infrastructure security guards"

if grep -q "raise ValueError" infrastructure/stacks/janus_stack.py 2>/dev/null; then
    pass "CDK stack has fail-fast guards for non-dev deployments"
else
    fail "CDK stack missing fail-fast guards for CORS/NEXTAUTH_SECRET"
fi

if grep -q "point_in_time_recovery" infrastructure/stacks/janus_stack.py 2>/dev/null; then
    pass "PITR configuration present in CDK stack"
else
    fail "PITR not configured in CDK stack"
fi

# ── Hardcoded secrets ────────────────────────────────────────────────────────
section "Hardcoded secrets check"

SECRET_HITS=$(grep -rn "dev-secret-minimum-32" backend/src/ infrastructure/ 2>/dev/null | grep -v "pyc" | wc -l | tr -d ' ')
if [ "$SECRET_HITS" -gt 0 ]; then
    warn "Dev secret string found in $SECRET_HITS location(s) — verify guards are in place"
else
    pass "No hardcoded dev secrets in source code"
fi

# ── Cross-file duplication (common patterns) ─────────────────────────────────
section "Cross-file duplication checks"

TIER_COLORS_COUNT="$(grep -rn "tierColors\|tier_colors" frontend/src/ --include="*.tsx" --include="*.ts" 2>/dev/null | grep -v "test\|node_modules\|import\|riskUtils" | grep -c "low.*moderate.*high\|Record<string" 2>/dev/null || true)"
TIER_COLORS_COUNT="${TIER_COLORS_COUNT:-0}"
if [ "$TIER_COLORS_COUNT" -gt 1 ]; then
    fail "tierColors defined inline in $TIER_COLORS_COUNT files — should import from riskUtils.ts"
else
    pass "No duplicate tierColors definitions"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
if [ "$ERRORS" -gt 0 ]; then
    echo -e "${RED}Audit failed with $ERRORS error(s)${NC}"
    exit 1
else
    echo -e "${GREEN}Audit passed — no issues found${NC}"
fi
