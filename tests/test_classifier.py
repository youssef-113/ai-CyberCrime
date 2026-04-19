"""Tests for Classifier Service"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'classifier'))
from main import app, parse_classification

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_parse_classification():
    # Test valid JSON
    content = '{"crime_type": "blackmail", "confidence": 0.9, "reasoning": "test", "suggested_articles": [], "missing_evidence": []}'
    result = parse_classification(content)
    assert result["crime_type"] == "blackmail"
    assert result["confidence"] == 0.9

def test_parse_classification_with_markdown():
    # Test JSON in markdown code block
    content = '```json\n{"crime_type": "scam", "confidence": 0.8, "reasoning": "test", "suggested_articles": [], "missing_evidence": []}\n```'
    result = parse_classification(content)
    assert result["crime_type"] == "scam"
