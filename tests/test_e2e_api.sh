#!/bin/bash
PASS=0
FAIL=0
BASE="http://localhost:8000"

test_endpoint() {
  local desc="$1"
  local method="$2"
  local url="$3"
  local expect_status="${4:-200}"
  shift 4
  response=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "$url" "$@" 2>/dev/null)
  if [ "$response" = "$expect_status" ]; then
    echo "  PASS: $desc ($response)"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $desc (expected $expect_status, got $response)"
    FAIL=$((FAIL + 1))
  fi
}

echo "═══ ACEB End-to-End API Tests ═══"
echo ""

echo "-- 1. Backend Health --"
test_endpoint "Main health" GET "$BASE/health"
test_endpoint "API root" GET "$BASE/api/"
test_endpoint "API health" GET "$BASE/api/health"
test_endpoint "API aggregate health" GET "$BASE/api/health/aggregate"
test_endpoint "API ready" GET "$BASE/api/ready" 503
test_endpoint "API metrics" GET "$BASE/api/metrics"

echo ""
echo "-- 2. Sub-service Health --"
test_endpoint "OCR health" GET "$BASE/ocr/health"
test_endpoint "Classifier health" GET "$BASE/classifier/health"
test_endpoint "RAG health" GET "$BASE/rag/health"
test_endpoint "Verification health" GET "$BASE/verification/health"
test_endpoint "PDF health" GET "$BASE/pdf/health"
test_endpoint "Chat health" GET "$BASE/chat/health"

echo ""
echo "-- 3. Protected (expect 401) --"
test_endpoint "Tenants" GET "$BASE/api/tenants" 401
test_endpoint "Cases" GET "$BASE/api/cases" 401
test_endpoint "Stats" GET "$BASE/api/stats" 401
test_endpoint "Analyze JSON" POST "$BASE/api/analyze/json" 401
test_endpoint "Classify" POST "$BASE/api/classify" 401
test_endpoint "Retrieve" POST "$BASE/api/retrieve" 401
test_endpoint "Verify" POST "$BASE/api/verify" 401
test_endpoint "OCR engines" GET "$BASE/api/ocr/engines/status" 401

echo ""
echo "-- 4. Frontend --"
test_endpoint "Frontend serves" GET "http://localhost:3000/"

echo ""
echo "═══ Results: $PASS passed, $FAIL failed ═══"
echo ""
docker ps --filter "name=ai-cybercrime" --format "table {{.Names}}\t{{.Status}}"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
