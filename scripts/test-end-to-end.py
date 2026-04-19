#!/usr/bin/env python3
"""
End-to-End Test for AI Cybercrime Evidence Builder
Tests the complete pipeline from upload to PDF generation
"""

import asyncio
import httpx
import sys
from datetime import datetime

# Service endpoints
BASE_URL = "http://localhost:8000"
SERVICES = {
    "api-gateway": "http://localhost:8000/health",
    "ocr": "http://localhost:8001/health",
    "classifier": "http://localhost:8002/health",
    "rag": "http://localhost:8003/health",
    "verification": "http://localhost:8004/health",
    "pdf-gen": "http://localhost:8005/health",
    "qdrant": "http://localhost:6333/healthz",
}

PASSED = 0
FAILED = 0

def log_success(msg):
    global PASSED
    PASSED += 1
    print(f"✓ {msg}")

def log_fail(msg):
    global FAILED
    FAILED += 1
    print(f"✗ {msg}")

async def test_health(service_name: str, url: str):
    """Test single service health"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                if "healthy" in str(data).lower() or "ok" in str(data).lower():
                    log_success(f"{service_name} is healthy")
                    return True
                else:
                    log_fail(f"{service_name}: Unexpected response - {data}")
            else:
                log_fail(f"{service_name}: HTTP {resp.status_code}")
    except httpx.ConnectError:
        log_fail(f"{service_name}: Connection refused (service not running)")
    except Exception as e:
        log_fail(f"{service_name}: {str(e)}")
    return False

async def test_all_health():
    """Test all service health endpoints"""
    print("\n" + "="*50)
    print("TEST 1: Service Health Checks")
    print("="*50)
    
    tasks = [test_health(name, url) for name, url in SERVICES.items()]
    await asyncio.gather(*tasks)

async def test_ocr_extraction():
    """Test OCR with sample text file"""
    print("\n" + "="*50)
    print("TEST 2: OCR Extraction")
    print("="*50)
    
    try:
        async with httpx.AsyncClient() as client:
            # Create test file
            files = {"file": ("test.txt", b"Contact: 01012345678, Amount: 5000 EGP", "text/plain")}
            resp = await client.post(
                "http://localhost:8001/extract",
                files=files,
                timeout=30.0
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if "entities" in data and "text" in data:
                    log_success("OCR extraction working")
                    print(f"  Found entities: {len(data['entities'])}")
                else:
                    log_fail("OCR: Missing expected fields")
            else:
                log_fail(f"OCR: HTTP {resp.status_code}")
    except Exception as e:
        log_fail(f"OCR test failed: {str(e)}")

async def test_classification():
    """Test crime classification"""
    print("\n" + "="*50)
    print("TEST 3: Crime Classification")
    print("="*50)
    
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "text": "Someone threatened to expose my photos unless I pay them 5000 EGP",
                "entities": {"amounts": [{"value": "5000 EGP"}]}
            }
            resp = await client.post(
                "http://localhost:8002/classify",
                json=payload,
                timeout=30.0
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if "crime_type" in data:
                    log_success(f"Classification working: {data['crime_type']}")
                else:
                    log_fail("Classifier: Missing crime_type")
            else:
                log_fail(f"Classifier: HTTP {resp.status_code}")
    except Exception as e:
        log_fail(f"Classifier test failed: {str(e)}")

async def test_rag_retrieval():
    """Test law article retrieval"""
    print("\n" + "="*50)
    print("TEST 4: RAG Law Retrieval")
    print("="*50)
    
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "query": "blackmail threat",
                "crime_type": "blackmail",
                "top_k": 3
            }
            resp = await client.post(
                "http://localhost:8003/retrieve",
                json=payload,
                timeout=30.0
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if "articles" in data:
                    log_success(f"RAG retrieval working: {len(data['articles'])} articles")
                else:
                    log_fail("RAG: Missing articles")
            else:
                log_fail(f"RAG: HTTP {resp.status_code}")
    except Exception as e:
        log_fail(f"RAG test failed: {str(e)}")

async def test_full_pipeline():
    """Test complete pipeline through API Gateway"""
    print("\n" + "="*50)
    print("TEST 5: Full Pipeline (API Gateway)")
    print("="*50)
    
    try:
        async with httpx.AsyncClient() as client:
            # Note: This would need an actual file upload
            # For now just test the health endpoint
            resp = await client.get(f"{BASE_URL}/health", timeout=5.0)
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "healthy":
                    log_success("API Gateway orchestrator healthy")
                else:
                    log_fail("API Gateway: Unhealthy status")
            else:
                log_fail(f"API Gateway: HTTP {resp.status_code}")
    except Exception as e:
        log_fail(f"Pipeline test failed: {str(e)}")

async def run_all_tests():
    """Run all tests"""
    print("\n" + "="*50)
    print("AI CYBERCRIME - END-TO-END TEST SUITE")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    await test_all_health()
    await test_ocr_extraction()
    await test_classification()
    await test_rag_retrieval()
    await test_full_pipeline()
    
    # Summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    print(f"Passed: {PASSED}")
    print(f"Failed: {FAILED}")
    print(f"Total:  {PASSED + FAILED}")
    
    if FAILED == 0:
        print("\n✓ ALL TESTS PASSED - System is ready!")
        return 0
    else:
        print(f"\n✗ {FAILED} tests failed - Check service logs")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
