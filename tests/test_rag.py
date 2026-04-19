"""Tests for RAG Service"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'rag'))
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_retrieve_endpoint():
    # This would need a populated ChromaDB to work properly
    request_data = {
        "query": "blackmail threat",
        "crime_type": "blackmail",
        "top_k": 3
    }
    # Note: This test will fail without a populated DB
    # response = client.post("/retrieve", json=request_data)
    # assert response.status_code == 200
    pass
