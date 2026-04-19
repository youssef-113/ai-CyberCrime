#!/bin/bash
# Verification Script for AI Cybercrime Evidence Builder
# Tests all 8 services health endpoints

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Service endpoints
SERVICES=(
  "api-gateway:8000"
  "ocr:8001"
  "classifier:8002"
  "rag:8003"
  "verification:8004"
  "pdf-gen:8005"
  "frontend:3000"
  "qdrant:6333"
)

FAILED=0
PASSED=0

echo "=========================================="
echo "  AI Cybercrime - Service Health Check"
echo "=========================================="
echo ""

for service in "${SERVICES[@]}"; do
  IFS=':' read -r name port <<< "$service"
  
  echo -n "Testing $name (port $port)... "
  
  # Check if service is running
  if ! curl -s "http://localhost:$port" > /dev/null 2>&1; then
    echo -e "${RED}✗ NOT RUNNING${NC}"
    ((FAILED++))
    continue
  fi
  
  # Check health endpoint (skip frontend and qdrant which have different health paths)
  if [ "$name" == "frontend" ]; then
    # Frontend just needs to return HTML
    if curl -s "http://localhost:$port" | grep -q "html"; then
      echo -e "${GREEN}✓ OK${NC}"
      ((PASSED++))
    else
      echo -e "${YELLOW}⚠ CHECK MANUALLY${NC}"
    fi
  elif [ "$name" == "qdrant" ]; then
    # Qdrant health endpoint
    if curl -s "http://localhost:$port/healthz" | grep -q "ok"; then
      echo -e "${GREEN}✓ OK${NC}"
      ((PASSED++))
    else
      echo -e "${RED}✗ HEALTH CHECK FAILED${NC}"
      ((FAILED++))
    fi
  else
    # Standard health check for microservices
    response=$(curl -s "http://localhost:$port/health" 2>/dev/null || echo '{}')
    if echo "$response" | grep -q "healthy\|ok"; then
      echo -e "${GREEN}✓ OK${NC}"
      ((PASSED++))
    else
      echo -e "${RED}✗ HEALTH CHECK FAILED${NC}"
      echo "  Response: $response"
      ((FAILED++))
    fi
  fi
done

echo ""
echo "=========================================="
echo "  Results: $PASSED passed, $FAILED failed"
echo "=========================================="

if [ $FAILED -eq 0 ]; then
  echo -e "${GREEN}All services are healthy! ✓${NC}"
  exit 0
else
  echo -e "${RED}Some services failed. Check docker-compose logs.${NC}"
  echo "Run: docker-compose logs -f [service-name]"
  exit 1
fi
