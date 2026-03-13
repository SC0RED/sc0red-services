#!/usr/bin/env bash
#
# End-to-end integration test for Janus.
# Runs the full flow: register → login → scan start → confirm → poll → view → delete.
#
# Usage:
#   # Standard (standalone DynamoDB, no SQS worker — auth tests only):
#   ./scripts/e2e-test.sh
#
#   # Full E2E with async scan flow (requires docker-compose.e2e.yml):
#   GH_TOKEN=$(gh auth token) docker compose -f docker-compose.e2e.yml up --build -d
#   BACKEND_URL=http://localhost:8001 E2E_MODE=full ./scripts/e2e-test.sh
#
# Prerequisites: python3 with boto3 and PyJWT installed
#   python3 -m pip install boto3 PyJWT
#
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8001}"
NEXTAUTH_SECRET="${NEXTAUTH_SECRET:-dev-secret-minimum-32-characters-long}"
DYNAMODB_ENDPOINT="${DYNAMODB_ENDPOINT:-http://localhost:8000}"
DYNAMODB_TABLE="${DYNAMODB_TABLE:-janus-dev}"
AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL:-}"
# Set E2E_MODE=full to enable scan + async polling tests (requires docker-compose.e2e.yml)
E2E_MODE="${E2E_MODE:-basic}"
# URL of the mock company website — must be reachable from inside the backend container
MOCK_COMPANY_URL="${MOCK_COMPANY_URL:-http://ai-mock:8080/company}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

pass=0
fail=0

assert_status() {
    local label="$1" expected="$2" actual="$3"
    if [ "$actual" -eq "$expected" ]; then
        echo -e "  ${GREEN}✓${NC} $label (HTTP $actual)"
        pass=$((pass + 1))
    else
        echo -e "  ${RED}✗${NC} $label — expected $expected, got $actual"
        fail=$((fail + 1))
    fi
}

assert_json() {
    local label="$1" field="$2" expected="$3" body="$4"
    actual=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('$field',''))" 2>/dev/null || echo "PARSE_ERROR")
    if [ "$actual" = "$expected" ]; then
        echo -e "  ${GREEN}✓${NC} $label ($field=$actual)"
        pass=$((pass + 1))
    else
        echo -e "  ${RED}✗${NC} $label — expected $field=$expected, got $actual"
        fail=$((fail + 1))
    fi
}

assert_json_nonempty() {
    local label="$1" field="$2" body="$3"
    actual=$(echo "$body" | python3 -c "import sys,json; v=json.load(sys.stdin).get('$field',''); print(bool(v))" 2>/dev/null || echo "False")
    if [ "$actual" = "True" ]; then
        echo -e "  ${GREEN}✓${NC} $label ($field is set)"
        pass=$((pass + 1))
    else
        echo -e "  ${RED}✗${NC} $label — expected $field to be non-empty"
        fail=$((fail + 1))
    fi
}

# ── Wait for backend ──────────────────────────────────────────────
echo -e "${YELLOW}Waiting for backend at $BACKEND_URL ...${NC}"
for i in $(seq 1 30); do
    if curl -sf "$BACKEND_URL/api/health" > /dev/null 2>&1; then
        echo -e "${GREEN}Backend is ready${NC}"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo -e "${RED}Backend did not start in time${NC}"
        exit 1
    fi
    sleep 2
done

# ── Create DynamoDB table ────────────────────────────────────────
echo -e "\n${YELLOW}Ensuring DynamoDB table exists ...${NC}"
python3 -c "
import boto3, os
endpoint = os.environ.get('DYNAMODB_ENDPOINT', 'http://localhost:8000')
table = os.environ.get('DYNAMODB_TABLE', 'janus-dev')
ddb = boto3.client('dynamodb', endpoint_url=endpoint, region_name='us-east-1',
    aws_access_key_id='local', aws_secret_access_key='local')
try:
    ddb.create_table(
        TableName=table,
        KeySchema=[{'AttributeName':'pk','KeyType':'HASH'},{'AttributeName':'sk','KeyType':'RANGE'}],
        AttributeDefinitions=[
            {'AttributeName':'pk','AttributeType':'S'},{'AttributeName':'sk','AttributeType':'S'},
            {'AttributeName':'GSI1PK','AttributeType':'S'},{'AttributeName':'GSI1SK','AttributeType':'S'},
            {'AttributeName':'GSI2PK','AttributeType':'S'},{'AttributeName':'GSI2SK','AttributeType':'S'},
            {'AttributeName':'GSI3PK','AttributeType':'S'},{'AttributeName':'GSI3SK','AttributeType':'S'},
            {'AttributeName':'GSI4PK','AttributeType':'S'},{'AttributeName':'GSI4SK','AttributeType':'S'},
        ],
        GlobalSecondaryIndexes=[
            {'IndexName':'GSI1','KeySchema':[{'AttributeName':'GSI1PK','KeyType':'HASH'},{'AttributeName':'GSI1SK','KeyType':'RANGE'}],'Projection':{'ProjectionType':'ALL'}},
            {'IndexName':'GSI2','KeySchema':[{'AttributeName':'GSI2PK','KeyType':'HASH'},{'AttributeName':'GSI2SK','KeyType':'RANGE'}],'Projection':{'ProjectionType':'ALL'}},
            {'IndexName':'GSI3','KeySchema':[{'AttributeName':'GSI3PK','KeyType':'HASH'},{'AttributeName':'GSI3SK','KeyType':'RANGE'}],'Projection':{'ProjectionType':'ALL'}},
            {'IndexName':'GSI4','KeySchema':[{'AttributeName':'GSI4PK','KeyType':'HASH'},{'AttributeName':'GSI4SK','KeyType':'RANGE'}],'Projection':{'ProjectionType':'ALL'}},
        ],
        BillingMode='PAY_PER_REQUEST',
    )
    print(f'Table {table} created')
except ddb.exceptions.ResourceInUseException:
    print(f'Table {table} already exists')
" 2>&1

# ── Create SQS queue (E2E mode only) ─────────────────────────────
if [ "$E2E_MODE" = "full" ]; then
    echo -e "\n${YELLOW}Ensuring SQS queue exists ...${NC}"
    python3 -c "
import boto3, os
endpoint = os.environ.get('AWS_ENDPOINT_URL', 'http://localhost:4566')
sqs = boto3.client('sqs', endpoint_url=endpoint, region_name='us-east-1',
    aws_access_key_id='local', aws_secret_access_key='local')
response = sqs.create_queue(QueueName='janus-analysis-e2e')
print('Queue URL:', response['QueueUrl'])
" 2>&1
fi

EMAIL="e2e-$(date +%s)@test.com"
PASSWORD='TestPass1234'

# ── 1. Register ──────────────────────────────────────────────────
echo -e "\n${YELLOW}1. Register${NC}"
RESP=$(curl -sw "\n%{http_code}" -X POST "$BACKEND_URL/api/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"E2E User\",\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"orgName\":\"E2E Org\"}")
BODY=$(echo "$RESP" | sed '$d')
STATUS=$(echo "$RESP" | tail -n 1)
assert_status "Register" 200 "$STATUS"
assert_json "Register success" "success" "True" "$BODY"

# ── 2. Login ─────────────────────────────────────────────────────
echo -e "\n${YELLOW}2. Login${NC}"
RESP=$(curl -sw "\n%{http_code}" -X POST "$BACKEND_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
BODY=$(echo "$RESP" | sed '$d')
STATUS=$(echo "$RESP" | tail -n 1)
assert_status "Login" 200 "$STATUS"
assert_json "Login success" "success" "True" "$BODY"

# Extract user info for JWT
USER_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['user']['id'])")
ORG_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['user']['orgId'])")

# Create a JWT for authenticated requests
TOKEN=$(python3 -c "
import jwt, time
payload = {'id':'$USER_ID','email':'$EMAIL','orgId':'$ORG_ID','role':'admin','name':'E2E User','exp':int(time.time())+300}
print(jwt.encode(payload, '$NEXTAUTH_SECRET', algorithm='HS256'))
")

AUTH="Authorization: Bearer $TOKEN"

# ── 3. Dashboard (empty) ────────────────────────────────────────
echo -e "\n${YELLOW}3. Dashboard (empty)${NC}"
RESP=$(curl -sw "\n%{http_code}" "$BACKEND_URL/api/dashboard" -H "$AUTH")
BODY=$(echo "$RESP" | sed '$d')
STATUS=$(echo "$RESP" | tail -n 1)
assert_status "Dashboard" 200 "$STATUS"
assert_json "No analyses" "totalAnalyses" "0" "$BODY"

# ── 4. List analyses (empty) ────────────────────────────────────
echo -e "\n${YELLOW}4. List analyses (empty)${NC}"
RESP=$(curl -sw "\n%{http_code}" "$BACKEND_URL/api/analyses" -H "$AUTH")
STATUS=$(echo "$RESP" | tail -n 1)
assert_status "List analyses" 200 "$STATUS"

# ── 5. Login with wrong password ────────────────────────────────
echo -e "\n${YELLOW}5. Login with wrong password${NC}"
RESP=$(curl -sw "\n%{http_code}" -X POST "$BACKEND_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"wrong\"}")
STATUS=$(echo "$RESP" | tail -n 1)
assert_status "Bad credentials" 401 "$STATUS"

# ── 6. Unauthenticated access ───────────────────────────────────
echo -e "\n${YELLOW}6. Unauthenticated access${NC}"
RESP=$(curl -sw "\n%{http_code}" "$BACKEND_URL/api/dashboard")
STATUS=$(echo "$RESP" | tail -n 1)
assert_status "No auth = 401" 401 "$STATUS"

# ── Scan flow (E2E_MODE=full only) ──────────────────────────────
if [ "$E2E_MODE" = "full" ]; then

    # ── 7. Single scan (async via SQS) ────────────────────────────
    echo -e "\n${YELLOW}7. Single scan start (async via SQS)${NC}"
    RESP=$(curl -sw "\n%{http_code}" -X POST "$BACKEND_URL/api/scan/start" \
        -H "Content-Type: application/json" \
        -H "$AUTH" \
        -d "{\"url\":\"$MOCK_COMPANY_URL\",\"type\":\"single\"}")
    BODY=$(echo "$RESP" | sed '$d')
    STATUS=$(echo "$RESP" | tail -n 1)
    assert_status "Single scan start" 200 "$STATUS"
    assert_json "Single scan enqueued" "status" "running" "$BODY"
    assert_json_nonempty "Got scanId" "scanId" "$BODY"
    assert_json_nonempty "Got analysisId" "analysisId" "$BODY"
    SINGLE_SCAN_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['scanId'])")
    ANALYSIS_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['analysisId'])")

    # ── 7b. Poll until single scan completes ────────────────────
    echo -e "\n${YELLOW}7b. Poll single scan until complete (max 120s)${NC}"
    SINGLE_COMPLETE=false
    for i in $(seq 1 40); do
        RESP=$(curl -sw "\n%{http_code}" "$BACKEND_URL/api/scan/$SINGLE_SCAN_ID" -H "$AUTH")
        SCAN_STATUS=$(echo "$RESP" | sed '$d' | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
        echo -e "    Poll $i: status=$SCAN_STATUS"
        if [ "$SCAN_STATUS" = "complete" ]; then
            SINGLE_COMPLETE=true
            break
        fi
        sleep 3
    done

    if [ "$SINGLE_COMPLETE" = "true" ]; then
        echo -e "  ${GREEN}✓${NC} Single scan reached complete status"
        pass=$((pass + 1))
    else
        echo -e "  ${RED}✗${NC} Single scan did not complete within 120s"
        fail=$((fail + 1))
    fi

    # ── 8. Verify single scan analysis has risk score ─────────────
    echo -e "\n${YELLOW}8. Verify single scan analysis${NC}"
    RESP=$(curl -sw "\n%{http_code}" "$BACKEND_URL/api/analysis/$ANALYSIS_ID" -H "$AUTH")
    BODY=$(echo "$RESP" | sed '$d')
    STATUS=$(echo "$RESP" | tail -n 1)
    assert_status "Get analysis" 200 "$STATUS"
    assert_json_nonempty "Analysis has companyName" "companyName" "$BODY"
    assert_json_nonempty "Analysis has overallRiskScore" "overallRiskScore" "$BODY"

    # ── 9. Async confirm → SQS → worker path ─────────────────────
    # Start a second scan for the portfolio confirm flow
    echo -e "\n${YELLOW}9. Start scan for async confirm test${NC}"
    RESP=$(curl -sw "\n%{http_code}" -X POST "$BACKEND_URL/api/scan/start" \
        -H "Content-Type: application/json" \
        -H "$AUTH" \
        -d "{\"url\":\"$MOCK_COMPANY_URL\",\"type\":\"single\"}")
    BODY=$(echo "$RESP" | sed '$d')
    ASYNC_SCAN_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('scanId',''))" 2>/dev/null || echo "")

    # ── 10. Confirm scan via async SQS path ───────────────────────
    echo -e "\n${YELLOW}10. Confirm scan (async 202 → SQS → worker)${NC}"
    RESP=$(curl -sw "\n%{http_code}" -X POST "$BACKEND_URL/api/scan/$ASYNC_SCAN_ID/confirm" \
        -H "Content-Type: application/json" \
        -H "$AUTH" \
        -d "{\"companies\":[{\"name\":\"Async Corp\",\"url\":\"$MOCK_COMPANY_URL\"}]}")
    BODY=$(echo "$RESP" | sed '$d')
    STATUS=$(echo "$RESP" | tail -n 1)
    assert_status "Confirm returns 202" 202 "$STATUS"
    assert_json "Confirm ok" "ok" "True" "$BODY"

    ASYNC_ANALYSIS_ID=$(echo "$BODY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
queued = data.get('queued', [])
print(queued[0]['analysisId'] if queued else '')
" 2>/dev/null || echo "")
    if [ -z "$ASYNC_ANALYSIS_ID" ]; then
        echo -e "  ${RED}✗${NC} No analysisId in confirm response"
        fail=$((fail + 1))
    else
        echo -e "  ${GREEN}✓${NC} Got async analysisId"
        pass=$((pass + 1))
    fi

    # ── 11. Poll until async scan completes ───────────────────────
    echo -e "\n${YELLOW}11. Poll async scan until complete (max 120s)${NC}"
    SCAN_COMPLETE=false
    for i in $(seq 1 40); do
        RESP=$(curl -sw "\n%{http_code}" "$BACKEND_URL/api/scan/$ASYNC_SCAN_ID" -H "$AUTH")
        SCAN_STATUS=$(echo "$RESP" | sed '$d' | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
        echo -e "    Poll $i: status=$SCAN_STATUS"
        if [ "$SCAN_STATUS" = "complete" ]; then
            SCAN_COMPLETE=true
            break
        fi
        sleep 3
    done

    if [ "$SCAN_COMPLETE" = "true" ]; then
        echo -e "  ${GREEN}✓${NC} Async scan reached complete status"
        pass=$((pass + 1))
    else
        echo -e "  ${RED}✗${NC} Async scan did not complete within timeout"
        fail=$((fail + 1))
    fi

    # ── 12. Verify async analysis has risk score ──────────────────
    echo -e "\n${YELLOW}12. Verify async analysis results${NC}"
    RESP=$(curl -sw "\n%{http_code}" "$BACKEND_URL/api/scan/$ASYNC_SCAN_ID" -H "$AUTH")
    BODY=$(echo "$RESP" | sed '$d')
    STATUS=$(echo "$RESP" | tail -n 1)
    assert_status "Async scan status endpoint" 200 "$STATUS"
    HAS_SCORE=$(echo "$BODY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
analyses = data.get('analyses', [])
print(any(a.get('overallRiskScore') is not None for a in analyses))
" 2>/dev/null || echo "False")
    if [ "$HAS_SCORE" = "True" ]; then
        echo -e "  ${GREEN}✓${NC} Async analysis has overallRiskScore"
        pass=$((pass + 1))
    else
        echo -e "  ${RED}✗${NC} No risk score found in async analysis"
        fail=$((fail + 1))
    fi

    # ── 13. Dashboard shows updated stats ─────────────────────────
    echo -e "\n${YELLOW}13. Dashboard after scans${NC}"
    RESP=$(curl -sw "\n%{http_code}" "$BACKEND_URL/api/dashboard" -H "$AUTH")
    BODY=$(echo "$RESP" | sed '$d')
    STATUS=$(echo "$RESP" | tail -n 1)
    assert_status "Dashboard" 200 "$STATUS"
    TOTAL=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('totalAnalyses',0))" 2>/dev/null || echo "0")
    if [ "$TOTAL" -ge 2 ]; then
        echo -e "  ${GREEN}✓${NC} Dashboard totalAnalyses=$TOTAL"
        pass=$((pass + 1))
    else
        echo -e "  ${RED}✗${NC} Dashboard shows $TOTAL analyses (expected ≥ 2)"
        fail=$((fail + 1))
    fi

    # ── 14. Delete analysis ───────────────────────────────────────
    echo -e "\n${YELLOW}14. Delete analysis${NC}"
    RESP=$(curl -sw "\n%{http_code}" -X DELETE "$BACKEND_URL/api/analysis/$ANALYSIS_ID" -H "$AUTH")
    STATUS=$(echo "$RESP" | tail -n 1)
    assert_status "Delete analysis" 200 "$STATUS"

    # ── 15. Verify deletion ───────────────────────────────────────
    echo -e "\n${YELLOW}15. Verify analysis is gone${NC}"
    RESP=$(curl -sw "\n%{http_code}" "$BACKEND_URL/api/analysis/$ANALYSIS_ID" -H "$AUTH")
    STATUS=$(echo "$RESP" | tail -n 1)
    assert_status "Analysis 404 after delete" 404 "$STATUS"

    # ── 16. Dashboard scan has createdAt ────────────────────────
    echo -e "\n${YELLOW}16. Dashboard scan has createdAt${NC}"
    RESP=$(curl -sw "\n%{http_code}" "$BACKEND_URL/api/dashboard" -H "$AUTH")
    BODY=$(echo "$RESP" | sed '$d')
    HAS_DATE=$(echo "$BODY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
scans = data.get('recentScans', [])
print(any(s.get('createdAt') for s in scans))
" 2>/dev/null || echo "False")
    if [ "$HAS_DATE" = "True" ]; then
        echo -e "  ${GREEN}✓${NC} Dashboard scan has createdAt timestamp"
        pass=$((pass + 1))
    else
        echo -e "  ${RED}✗${NC} Dashboard scan missing createdAt"
        fail=$((fail + 1))
    fi

    # ── 17. Delete scan (cascade) ───────────────────────────────
    echo -e "\n${YELLOW}17. Delete scan (cascade)${NC}"
    RESP=$(curl -sw "\n%{http_code}" -X DELETE "$BACKEND_URL/api/scan/$ASYNC_SCAN_ID" -H "$AUTH")
    BODY=$(echo "$RESP" | sed '$d')
    STATUS=$(echo "$RESP" | tail -n 1)
    assert_status "Delete scan" 200 "$STATUS"
    assert_json "Delete scan ok" "ok" "True" "$BODY"

    # ── 18. Verify scan is gone ─────────────────────────────────
    echo -e "\n${YELLOW}18. Verify scan is gone${NC}"
    RESP=$(curl -sw "\n%{http_code}" "$BACKEND_URL/api/scan/$ASYNC_SCAN_ID" -H "$AUTH")
    STATUS=$(echo "$RESP" | tail -n 1)
    assert_status "Scan 404 after delete" 404 "$STATUS"

    # ── 19. Verify cascade — async analysis also gone ───────────
    echo -e "\n${YELLOW}19. Verify cascade — async analysis deleted${NC}"
    RESP=$(curl -sw "\n%{http_code}" "$BACKEND_URL/api/analysis/$ASYNC_ANALYSIS_ID" -H "$AUTH")
    STATUS=$(echo "$RESP" | tail -n 1)
    assert_status "Cascaded analysis 404" 404 "$STATUS"

fi  # E2E_MODE=full

# ── Summary ──────────────────────────────────────────────────────
echo ""
echo "================================"
echo -e "${GREEN}Passed: $pass${NC}"
if [ "$fail" -gt 0 ]; then
    echo -e "${RED}Failed: $fail${NC}"
    echo "================================"
    exit 1
else
    echo -e "${GREEN}All tests passed!${NC}"
    echo "================================"
fi
