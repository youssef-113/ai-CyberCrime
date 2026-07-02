import base64
import json
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import services.database.database as db_module
from services.api import main as api_main


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeDb:
    def __init__(self):
        self.updated = None

    def table(self, name):
        return self

    def update(self, data):
        self.updated = data
        return self

    def eq(self, key, value):
        self.eq_key = (key, value)
        return self

    def execute(self):
        return SimpleNamespace(data=[{"ok": True}])


@pytest.mark.asyncio
async def test_download_pdf_parses_stringified_result(monkeypatch):
    case = {
        "case_id": "CASE_TEST",
        "user_id": "user-1",
        "status": "completed",
        "result": json.dumps(
            {
                "classification": {"crime_type": "blackmail"},
                "verification": {"timeline": [{"step": "review"}]},
                "timeline": [{"step": "review"}],
                "score": {"total_score": 85, "grade": "STRONG"},
                "articles": [],
            }
        ),
    }

    async def fake_get_case_by_id(case_id, user_id):
        assert case_id == "CASE_TEST"
        assert user_id == "user-1"
        return case

    async def fake_call_microservice(*args, **kwargs):
        return FakeResponse(
            {
                "status": "generated",
                "path": "/tmp/test.pdf",
                "pdf_base64": base64.b64encode(b"%PDF-1.4").decode(),
            }
        )

    fake_db = FakeDb()

    monkeypatch.setattr(api_main, "get_case_by_id", fake_get_case_by_id)
    monkeypatch.setattr(api_main, "call_microservice", fake_call_microservice)
    monkeypatch.setattr(db_module, "get_supabase", lambda: fake_db)

    response = await api_main.download_pdf("CASE_TEST", user_id="user-1")

    assert response.media_type == "application/pdf"
    assert response.body == b"%PDF-1.4"
    assert fake_db.updated["pdf_path"] == "/tmp/test.pdf"
