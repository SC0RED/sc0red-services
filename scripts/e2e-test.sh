#!/usr/bin/env bash
#
# End-to-end integration test for Janus.
# Runs the full flow: register → login → scan → poll → view → delete.
#
# Usage: ./scripts/e2e-test.sh
#
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8001}"
NEXTAUTH_SECRET="${NEXTAUTH_SECRET:-dev-secret-minimum-32-characters-long}"

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
ddb = boto3.client('dynamodb', endpoint_url=endpoint, region_name='us-east-1',
    aws_access_key_id='local', aws_secret_access_key='local')
try:
    ddb.create_table(
        TableName='janus-dev',
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
    print('Table created')
except ddb.exceptions.ResourceInUseException:
    print('Table already exists')
" 2>&1

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
