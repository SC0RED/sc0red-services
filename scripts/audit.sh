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

if grep -rq "raise ValueError" infrastructure/stacks/ 2>/dev/null; then
    pass "CDK stack has fail-fast guards for non-dev deployments"
else
    fail "CDK stack missing fail-fast guards for CORS/NEXTAUTH_SECRET"
fi

if grep -rq "point_in_time_recovery" infrastructure/stacks/ 2>/dev/null; then
    pass "PITR configuration present in CDK stack"
else
    fail "PITR not configured in CDK stack"
fi

if grep -rq "throttling_rate_limit" infrastructure/stacks/ 2>/dev/null; then
    pass "API rate limiting configured in CDK stack"
else
    fail "API rate limiting (throttling_rate_limit) not configured in CDK stack"
fi

if grep -rq "DlqAlarm" infrastructure/stacks/ 2>/dev/null; then
    pass "DLQ alarm configured in CDK stack"
else
    fail "DLQ alarm not configured in CDK stack"
fi

# ── Hardcoded secrets ────────────────────────────────────────────────────────
section "Hardcoded secrets check"

SECRET_HITS=$(grep -rn "dev-secret-minimum-32" backend/src/ infrastructure/ 2>/dev/null | grep -v "pyc" | wc -l | tr -d ' ' || echo "0")
if [ "$SECRET_HITS" -gt 0 ]; then
    warn "Dev secret string found in $SECRET_HITS location(s) — verify guards are in place"
else
    pass "No hardcoded dev secrets in source code"
fi

# ── Mandatory codebase patterns ──────────────────────────────────────────────
section "Mandatory codebase patterns"

# All AI calls must go through run_structured_ai_call (not direct client.query_structured)
# Exclude: ai_call.py (the shared module), tests, comments/docstrings (lines with #, ..., or leading spaces+text)
DIRECT_AI_CALLS="$(grep -rn "query_structured" backend/src/pipeline/ --include="*.py" 2>/dev/null | grep -v "ai_call.py\|test_\|__pycache__\|run_structured_ai_call\|#\|\.\.\." | grep -v "^$" || true)"
if [ -n "$DIRECT_AI_CALLS" ]; then
    fail "Direct query_structured calls found outside ai_call.py — must use run_structured_ai_call:"
    echo "$DIRECT_AI_CALLS" | head -5 | while read -r line; do echo "    $line"; done
else
    pass "All pipeline AI calls go through run_structured_ai_call"
fi

# All parallel work must use FutureManager (not ThreadPoolExecutor)
THREAD_POOL="$(grep -rn "ThreadPoolExecutor" backend/src/ --include="*.py" 2>/dev/null | grep -v "test_\|__pycache__" || true)"
if [ -n "$THREAD_POOL" ]; then
    fail "ThreadPoolExecutor found in source — must use FutureManager:"
    echo "$THREAD_POOL" | head -5 | while read -r line; do echo "    $line"; done
else
    pass "No ThreadPoolExecutor in source (FutureManager used for parallel work)"
fi

# All AI prompts must be in prompts/ directory (not inline in Python)
INLINE_PROMPTS="$(grep -rn 'SYSTEM_PROMPT\s*=' backend/src/pipeline/ --include="*.py" 2>/dev/null | grep -v "prompts/\|load_system_prompt\|test_\|__pycache__\|ai_guides/" || true)"
if [ -n "$INLINE_PROMPTS" ]; then
    fail "Inline system prompt definitions found — must use prompts/*.md files:"
    echo "$INLINE_PROMPTS" | head -5 | while read -r line; do echo "    $line"; done
else
    pass "All system prompts loaded from external files"
fi

# No inline HTML templates in Python (must be in templates/ directory)
INLINE_HTML="$(grep -rn '<!DOCTYPE html>\|<html>' backend/src/ --include="*.py" 2>/dev/null | grep -v "test_\|__pycache__" || true)"
if [ -n "$INLINE_HTML" ]; then
    fail "Inline HTML found in Python — must use external template files:"
    echo "$INLINE_HTML" | head -5 | while read -r line; do echo "    $line"; done
else
    pass "No inline HTML in Python (templates loaded from external files)"
fi

# ── Accessibility: skip-link target ───────────────────────────────────────────
section "Accessibility: pages with DashboardSidebar must have id=\"main\" on <main>"

SIDEBAR_PAGES_MISSING_MAIN=""
while IFS= read -r file; do
    if grep -q "DashboardSidebar" "$file" && ! grep -q 'id="main"' "$file"; then
        # Check if the file delegates to a client component that has id="main"
        dir="$(dirname "$file")"
        if ! grep -rq 'id="main"' "$dir"/*.tsx 2>/dev/null; then
            SIDEBAR_PAGES_MISSING_MAIN="$SIDEBAR_PAGES_MISSING_MAIN $file"
        fi
    fi
done < <(find frontend/src/app -name "*.tsx" -not -path "*/node_modules/*" -not -name "*.test.*")

if [ -n "$SIDEBAR_PAGES_MISSING_MAIN" ]; then
    for f in $SIDEBAR_PAGES_MISSING_MAIN; do
        fail "$f uses DashboardSidebar but missing id=\"main\" on <main> (skip-link target)"
    done
else
    pass "All pages with DashboardSidebar have id=\"main\" for skip-link"
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

# ── Data integrity: no silent default template on fact-bearing builders ──────
section "Data integrity: fact-bearing builders render a placeholder, not a default"

# Fact-bearing report sections (EBITDA tree, value chain) must never assert a
# fabricated existing fact (the customer-reported SaaS-default bug). FORWARD
# invariant: every fact-surface assembler — `assemble_*` (which builds the
# EBITDA tree / value chain from researched facts) — MUST carry an explicit
# insufficient-data branch (grounded=False) so an ungroundable input renders the
# placeholder, not a fabricated surface. Stated as a required-branch check so it
# can't be bypassed by renaming a helper or a constant.
# See openspec specs: report-data-integrity, value-chain-grounding, ebitda-tree-confidence.
MISSING_GROUNDED_BRANCH=""
while IFS= read -r f; do
    grep -Eq "def assemble_(ebitda_tree|value_chain)" "$f" 2>/dev/null || continue
    if ! grep -Eq "grounded[[:space:]]*=[[:space:]]*False|insufficient_data" "$f" 2>/dev/null; then
        MISSING_GROUNDED_BRANCH="$MISSING_GROUNDED_BRANCH $f"
    fi
done < <(find backend/src/pipeline/pipeline_steps -name '*.py' -not -name 'test_*' 2>/dev/null)

if [ -n "$MISSING_GROUNDED_BRANCH" ]; then
    for f in $MISSING_GROUNDED_BRANCH; do
        fail "$f has a fact-surface assembler with no insufficient-data (grounded=False) branch — fact-bearing sections must render a placeholder on no-match, not fabricate one"
    done
else
    pass "All fact-bearing assemblers have an insufficient-data placeholder branch"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
if [ "$ERRORS" -gt 0 ]; then
    echo -e "${RED}Audit failed with $ERRORS error(s)${NC}"
    exit 1
else
    echo -e "${GREEN}Audit passed — no issues found${NC}"
fi
