"""Tests for PDF Generation Service"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'pdf_gen'))
from main import app
from generate import generate_complaint_pdf

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_generate_pdf():
    pdf_bytes = generate_complaint_pdf(
        case_id="CASE_TEST001",
        crime_type="blackmail",
        evidence_summary="Test evidence summary",
        timeline=[{"date": "2024-01-15", "type": "threat", "description": "Threat received"}],
        law_articles=[{"article_number": "25", "law": "Law 175/2018", "text": "Test law text"}],
        score=85,
        grade="STRONG",
        complainant_name="Test User",
        language="ar"
    )
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 0
