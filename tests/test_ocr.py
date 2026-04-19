"""Tests for OCR Service"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'ocr'))
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "ocr"

def test_extract_entities():
    # Test entity extraction logic
    from main import extract_entities
    
    text = "Contact me on 01012345678. I need 5000 EGP transferred. Date: 15/01/2024"
    entities = extract_entities(text)
    
    assert len(entities["phones"]) == 1
    assert entities["phones"][0].value == "01012345678"
    assert len(entities["amounts"]) == 1
    assert len(entities["dates"]) == 1
