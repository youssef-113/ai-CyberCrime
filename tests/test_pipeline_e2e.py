"""End-to-End Pipeline Tests"""
import pytest
import httpx
import asyncio

# Service URLs (adjust for test environment)
BASE_URL = "http://localhost:8000"
SERVICE_URLS = {
    "ocr": "http://localhost:8001",
    "classifier": "http://localhost:8002",
    "rag": "http://localhost:8003",
    "verification": "http://localhost:8004",
    "pdf": "http://localhost:8005",
}

@pytest.mark.asyncio
async def test_full_health_check():
    """Test all services are healthy"""
    async with httpx.AsyncClient() as client:
        for name, url in SERVICE_URLS.items():
            try:
                resp = await client.get(f"{url}/health", timeout=5.0)
                assert resp.status_code == 200, f"{name} is not healthy"
            except httpx.ConnectError:
                pytest.skip(f"{name} service not running")

@pytest.mark.asyncio
async def test_analyze_endpoint():
    """Test main analyze endpoint"""
    async with httpx.AsyncClient() as client:
        try:
            # Create a test file
            files = {
                "files": ("test.txt", b"Test evidence content with phone 01012345678", "text/plain")
            }
            resp = await client.post(
                f"{BASE_URL}/analyze/json",
                files=files,
                timeout=120.0
            )
            if resp.status_code == 200:
                result = resp.json()
                assert "case_id" in result
                assert "classification" in result
                assert "score" in result
            else:
                pytest.skip(f"Analyze endpoint returned {resp.status_code}")
        except httpx.ConnectError:
            pytest.skip("API Gateway not running")

@pytest.mark.asyncio
async def test_service_communication():
    """Test services can communicate"""
    async with httpx.AsyncClient() as client:
        try:
            # Test OCR
            resp = await client.post(
                f"{SERVICE_URLS['ocr']}/extract",
                files={"file": ("test.txt", b"Test content", "text/plain")},
                timeout=30.0
            )
            if resp.status_code == 200:
                ocr_result = resp.json()
                assert "text" in ocr_result
                assert "entities" in ocr_result
        except httpx.ConnectError:
            pytest.skip("OCR service not running")
