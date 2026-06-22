#!/usr/bin/env python3
"""End-to-End API Tests for ACEB"""
import httpx
import json
import sys
import subprocess

PASS = 0
FAIL = 0
BASE = "http://localhost:8000"

def test_endpoint(desc, method, url, expect_status=200, **kwargs):
    global PASS, FAIL
    try:
        resp = httpx.request(method, url, timeout=30.0, **kwargs)
        if resp.status_code == expect_status:
            print(f"  PASS: {desc} ({resp.status_code})")
            PASS += 1
        else:
            print(f"  FAIL: {desc} (expected {expect_status}, got {resp.status_code})")
            try:
                print(f"    Body: {json.dumps(resp.json(), indent=2)[:200]}")
            except:
                pass
            FAIL += 1
    except Exception as e:
        print(f"  FAIL: {desc} (error: {e})")
        FAIL += 1

print("═══ ACEB End-to-End API Tests ═══\n")

print("-- 1. Backend Health --")
test_endpoint("Main health", "GET", f"{BASE}/health")
test_endpoint("API root", "GET", f"{BASE}/api/")
test_endpoint("API health", "GET", f"{BASE}/api/health")
test_endpoint("API aggregate health", "GET", f"{BASE}/api/health/aggregate")
test_endpoint("API ready", "GET", f"{BASE}/api/ready", 200)
test_endpoint("API metrics", "GET", f"{BASE}/api/metrics")

print("\n-- 2. Sub-service Health --")
test_endpoint("OCR health", "GET", f"{BASE}/ocr/health")
test_endpoint("Classifier health", "GET", f"{BASE}/classifier/health")
test_endpoint("RAG health", "GET", f"{BASE}/rag/health")
test_endpoint("Verification health", "GET", f"{BASE}/verification/health")
test_endpoint("PDF health", "GET", f"{BASE}/pdf/health")
test_endpoint("Chat health", "GET", f"{BASE}/chat/health")

print("\n-- 3. Protected Endpoints (expect 401) --")
test_endpoint("Tenants", "GET", f"{BASE}/api/tenants", 401)
test_endpoint("Cases", "GET", f"{BASE}/api/cases", 401)
test_endpoint("Stats", "GET", f"{BASE}/api/stats", 401)
test_endpoint("Analyze JSON", "POST", f"{BASE}/api/analyze/json", 401)
test_endpoint("Classify", "POST", f"{BASE}/api/classify", 401)
test_endpoint("Retrieve", "POST", f"{BASE}/api/retrieve", 401)
test_endpoint("Verify", "POST", f"{BASE}/api/verify", 401)
test_endpoint("OCR engines", "GET", f"{BASE}/api/ocr/engines/status", 401)

print("\n-- 4. Frontend --")
test_endpoint("Frontend serves", "GET", "http://localhost:3000/")

print("\n-- 5. Service Details --")
resp = httpx.get(f"{BASE}/chat/health", timeout=5.0)
print(f"  Chat: {resp.json().get('status','?')} / LLM: {resp.json().get('version','?')}")
resp = httpx.get(f"{BASE}/pdf/health", timeout=5.0)
print(f"  PDF: {resp.json().get('status','?')} / Outputs: {resp.json().get('outputs','?')}")
resp = httpx.get(f"{BASE}/classifier/health", timeout=5.0)
print(f"  Classifier: {resp.json().get('status','?')} / LLM: {resp.json().get('llm','?')}")
resp = httpx.get(f"{BASE}/rag/health", timeout=5.0)
print(f"  RAG: {resp.json().get('status','?')} / Chroma: {resp.json().get('chroma','?')}")

print(f"\n═══ Results: {PASS} passed, {FAIL} failed ═══\n")

result = subprocess.run(
    ["docker", "ps", "--filter", "name=ai-cybercrime", "--format", "table {{.Names}}\t{{.Status}}"],
    capture_output=True, text=True
)
print(result.stdout)

sys.exit(0 if FAIL == 0 else 1)
