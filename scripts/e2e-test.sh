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
python3 scripts/setup_dynamodb.py --table "$DYNAMODB_TABLE" --endpoint "$DYNAMODB_ENDPOINT"

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

    echo -e "\n${YELLOW}Ensuring S3 bucket exists ...${NC}"
    python3 -c "
import boto3, os
endpoint = os.environ.get('AWS_ENDPOINT_URL', 'http://localhost:4566')
s3 = boto3.client('s3', endpoint_url=endpoint, region_name='us-east-1',
    aws_access_key_id='local', aws_secret_access_key='local')
try:
    s3.create_bucket(Bucket='janus-documents-e2e')
    print('Bucket janus-documents-e2e created')
except s3.exceptions.BucketAlreadyOwnedByYou:
    print('Bucket janus-documents-e2e already exists')
except Exception as e:
    if 'BucketAlreadyOwnedByYou' in str(e) or 'BucketAlreadyExists' in str(e):
        print('Bucket janus-documents-e2e already exists')
    else:
        raise
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

    # ── 8b. Verify EBITDA tree in analysis ──────────────────────
    echo -e "\n${YELLOW}8b. Verify EBITDA tree in analysis${NC}"
    HAS_EBITDA=$(echo "$BODY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tree = data.get('ebitdaTree')
if not tree:
    print('MISSING')
elif not tree.get('treeData'):
    print('EMPTY_TREE')
elif not tree.get('revenueEstimate'):
    print('NO_REVENUE')
elif not tree.get('ebitdaEstimate'):
    print('NO_EBITDA')
else:
    print('OK')
" 2>/dev/null || echo "ERROR")
    if [ "$HAS_EBITDA" = "OK" ]; then
        echo -e "  ${GREEN}✓${NC} Analysis has ebitdaTree with treeData, revenueEstimate, ebitdaEstimate"
        pass=$((pass + 1))
    else
        echo -e "  ${RED}✗${NC} EBITDA tree validation failed: $HAS_EBITDA"
        fail=$((fail + 1))
    fi

    EBITDA_NODE_COUNT=$(echo "$BODY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tree = data.get('ebitdaTree', {})
nodes = tree.get('treeData', [])
print(len(nodes))
" 2>/dev/null || echo "0")
    if [ "$EBITDA_NODE_COUNT" -ge 2 ]; then
        echo -e "  ${GREEN}✓${NC} EBITDA tree has $EBITDA_NODE_COUNT top-level nodes"
        pass=$((pass + 1))
    else
        echo -e "  ${RED}✗${NC} Expected ≥2 EBITDA nodes, got $EBITDA_NODE_COUNT"
        fail=$((fail + 1))
    fi

    # ── 8c. Verify value_lever on opportunities ─────────────────
    echo -e "\n${YELLOW}8c. Verify value_lever on opportunities${NC}"
    HAS_LEVER=$(echo "$BODY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
opps = data.get('opportunities', [])
if not opps:
    print('NO_OPPS')
elif any(o.get('value_lever') for o in opps):
    print('OK')
else:
    print('NO_LEVER')
" 2>/dev/null || echo "ERROR")
    if [ "$HAS_LEVER" = "OK" ]; then
        echo -e "  ${GREEN}✓${NC} Opportunities have value_lever set"
        pass=$((pass + 1))
    else
        echo -e "  ${RED}✗${NC} value_lever validation failed: $HAS_LEVER"
        fail=$((fail + 1))
    fi

    # ── 8d. Upload document via presigned URL ───────────────────
    echo -e "\n${YELLOW}8d. Upload document via presigned URL${NC}"
    RESP=$(curl -sw "\n%{http_code}" -X POST "$BACKEND_URL/api/analysis/$ANALYSIS_ID/upload-url" \
        -H "Content-Type: application/json" \
        -H "$AUTH" \
        -d '{"filename":"test-doc.txt","fileType":"txt"}')
    BODY=$(echo "$RESP" | sed '$d')
    STATUS=$(echo "$RESP" | tail -n 1)
    assert_status "Get upload URL" 200 "$STATUS"
    assert_json_nonempty "Got uploadUrl" "uploadUrl" "$BODY"
    assert_json_nonempty "Got documentKey" "documentKey" "$BODY"
    UPLOAD_URL=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['uploadUrl'])")
    DOC_KEY=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['documentKey'])")

    # Rewrite presigned URL: backend returns internal hostname (localstack:4566),
    # but E2E tests run on the host where LocalStack is at localhost:4566
    UPLOAD_URL=$(echo "$UPLOAD_URL" | sed 's|http://localstack:4566|http://localhost:4566|g' | sed 's|http://[^/]*\.localhost\.localstack\.cloud:4566|http://localhost:4566|g')

    # Upload file content to presigned URL
    echo -e "\n${YELLOW}8d-2. PUT file to presigned URL${NC}"
    PUT_STATUS=$(curl -sw "%{http_code}" -o /dev/null -X PUT "$UPLOAD_URL" \
        -H "Content-Type: application/octet-stream" \
        -d "This is a test document for E2E testing.")
    assert_status "PUT to presigned URL" 200 "$PUT_STATUS"

    # Register document with S3 key
    echo -e "\n${YELLOW}8d-3. Register document with S3 key${NC}"
    RESP=$(curl -sw "\n%{http_code}" -X POST "$BACKEND_URL/api/analysis/$ANALYSIS_ID/documents" \
        -H "Content-Type: application/json" \
        -H "$AUTH" \
        -d "{\"filename\":\"test-doc.txt\",\"fileType\":\"txt\",\"documentKey\":\"$DOC_KEY\"}")
    BODY=$(echo "$RESP" | sed '$d')
    STATUS=$(echo "$RESP" | tail -n 1)
    assert_status "Register document" 201 "$STATUS"
    assert_json_nonempty "Got document id" "id" "$BODY"
    DOC_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

    # Verify document appears in analysis
    echo -e "\n${YELLOW}8d-4. Verify document in analysis${NC}"
    RESP=$(curl -sw "\n%{http_code}" "$BACKEND_URL/api/analysis/$ANALYSIS_ID" -H "$AUTH")
    BODY=$(echo "$RESP" | sed '$d')
    DOC_COUNT=$(echo "$BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('documents',[])))" 2>/dev/null || echo "0")
    if [ "$DOC_COUNT" -ge 1 ]; then
        echo -e "  ${GREEN}✓${NC} Analysis has $DOC_COUNT document(s)"
        pass=$((pass + 1))
    else
        echo -e "  ${RED}✗${NC} Expected ≥1 documents, got $DOC_COUNT"
        fail=$((fail + 1))
    fi

    # ── 8e. Re-analyze with documents ────────────────────────────
    echo -e "\n${YELLOW}8e. Re-analyze with documents${NC}"
    RESP=$(curl -sw "\n%{http_code}" -X POST "$BACKEND_URL/api/analysis/$ANALYSIS_ID/reanalyze" \
        -H "$AUTH")
    BODY=$(echo "$RESP" | sed '$d')
    STATUS=$(echo "$RESP" | tail -n 1)
    assert_status "Reanalyze queued" 202 "$STATUS"
    assert_json "Reanalyze status" "status" "queued" "$BODY"

    # Wait for re-analysis to complete (poll the scan)
    echo -e "\n${YELLOW}8e-2. Wait for re-analysis to complete (max 120s)${NC}"
    REANALYZE_DONE=false
    for i in $(seq 1 40); do
        RESP=$(curl -sw "\n%{http_code}" "$BACKEND_URL/api/scan/$SINGLE_SCAN_ID" -H "$AUTH")
        SCAN_STATUS=$(echo "$RESP" | sed '$d' | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
        echo -e "    Poll $i: status=$SCAN_STATUS"
        if [ "$SCAN_STATUS" = "complete" ]; then
            REANALYZE_DONE=true
            break
        fi
        sleep 3
    done
    if [ "$REANALYZE_DONE" = "true" ]; then
        echo -e "  ${GREEN}✓${NC} Re-analysis completed"
        pass=$((pass + 1))
    else
        echo -e "  ${RED}✗${NC} Re-analysis did not complete within 120s"
        fail=$((fail + 1))
    fi

    # ── 8f. Delete document ──────────────────────────────────────
    echo -e "\n${YELLOW}8f. Delete document${NC}"
    RESP=$(curl -sw "\n%{http_code}" -X DELETE "$BACKEND_URL/api/analysis/$ANALYSIS_ID/documents/$DOC_ID" \
        -H "$AUTH")
    STATUS=$(echo "$RESP" | tail -n 1)
    assert_status "Delete document" 200 "$STATUS"

    # Verify document is gone
    RESP=$(curl -sw "\n%{http_code}" "$BACKEND_URL/api/analysis/$ANALYSIS_ID" -H "$AUTH")
    BODY=$(echo "$RESP" | sed '$d')
    DOC_COUNT=$(echo "$BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('documents',[])))" 2>/dev/null || echo "0")
    if [ "$DOC_COUNT" -eq 0 ]; then
        echo -e "  ${GREEN}✓${NC} Document deleted successfully"
        pass=$((pass + 1))
    else
        echo -e "  ${RED}✗${NC} Expected 0 documents after delete, got $DOC_COUNT"
        fail=$((fail + 1))
    fi

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
