"""Tests for Verification Service"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'verification'))
from main import app
from scoring import calculate_score
from timeline import build_timeline, classify_event

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200

def test_calculate_score():
    verification = {"final_status": "APPROVED"}
    entities = {
        "phones": [{"value": "01012345678"}],
        "amounts": [{"value": "5000 EGP"}],
        "dates": [{"value": "15/01/2024"}],
        "ocr_confidence": 0.9
    }
    
    score, breakdown = calculate_score(verification, entities, article_count=2)
    assert score > 0
    assert "grade" in breakdown
    assert score >= 75 and breakdown["grade"] == "STRONG" or score < 75

def test_classify_event():
    assert classify_event("He threatened to expose photos") == "threat"
    assert classify_event("Send money now") == "financial"
    assert classify_event("Message me") == "communication"

def test_build_timeline():
    text = "On 15/01/2024 he sent a threat. On 16/01/2024 he demanded money."
    entities = {"dates": [{"value": "15/01/2024"}, {"value": "16/01/2024"}]}
    timeline = build_timeline(text, entities)
    assert len(timeline) > 0
