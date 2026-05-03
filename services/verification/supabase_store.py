"""Supabase-backed Verification Store – cloud persistence for audit trail.

Falls back to SQLite when Supabase is not configured.
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .database import VerificationStore as SQLiteStore

logger = logging.getLogger("verification.store")

# ── Supabase client (lazy) ──────────────────────────────────────────────

_supabase_client = None


def _get_supabase():
    """Lazy-init Supabase client using env vars."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")

    if not url or not key:
        return None

    try:
        from supabase import create_client
        _supabase_client = create_client(url, key)
        logger.info("Supabase client initialized for verification store")
        return _supabase_client
    except ImportError:
        logger.warning("supabase-py not installed; falling back to SQLite")
        return None
    except Exception as e:
        logger.error("Failed to init Supabase client: %s", e)
        return None


class SupabaseVerificationStore:
    """Persist verification cases and rounds to Supabase Postgres.

    If Supabase is unavailable, silently falls back to the local SQLite store
    so the service never blocks on a cloud outage.
    """

    def __init__(self, sqlite_path: str = "data/verification.db"):
        self._sqlite = SQLiteStore(db_path=sqlite_path)
        self._sb = None  # resolved lazily on first write

    def _sb_or_fallback(self):
        """Return Supabase client or None (caller falls back to SQLite)."""
        if self._sb is None:
            self._sb = _get_supabase()
        return self._sb

    # ── case-level ops ────────────────────────────────────────────────────

    def create_case(
        self,
        case_id: str,
        crime_type: str,
        user_id: Optional[str] = None,
        source_case_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        sb = self._sb_or_fallback()
        if sb:
            try:
                data: Dict[str, any] = {
                    "case_id": case_id,
                    "crime_type": crime_type,
                }
                if user_id:
                    data["user_id"] = user_id
                if source_case_id:
                    data["source_case_id"] = source_case_id
                if session_id:
                    data["session_id"] = session_id
                sb.table("verification_cases").insert(data).execute()
                logger.debug("Supabase: created case %s (user=%s)", case_id, user_id)
            except Exception as e:
                logger.error("Supabase create_case failed: %s – falling back to SQLite", e)
        # Always write to SQLite as local cache / fallback
        self._sqlite.create_case(case_id, crime_type, user_id, source_case_id, session_id)

    def update_case_status(
        self,
        case_id: str,
        final_status: str,
        final_score: int,
        total_rounds: int,
        grade: str,
    ) -> None:
        sb = self._sb_or_fallback()
        if sb:
            try:
                sb.table("verification_cases").update({
                    "final_status": final_status,
                    "final_score": final_score,
                    "total_rounds": total_rounds,
                    "grade": grade,
                }).eq("case_id", case_id).execute()
                logger.debug("Supabase: updated case %s → %s", case_id, final_status)
            except Exception as e:
                logger.error("Supabase update_case_status failed: %s – falling back to SQLite", e)
        self._sqlite.update_case_status(case_id, final_status, final_score, total_rounds, grade)

    def get_case_summary(self, case_id: str) -> Optional[Dict]:
        sb = self._sb_or_fallback()
        if sb:
            try:
                result = sb.table("verification_cases").select("*").eq("case_id", case_id).execute()
                if result.data:
                    row = result.data[0]
                    return {
                        "case_id": row["case_id"],
                        "user_id": row.get("user_id"),
                        "source_case_id": row.get("source_case_id"),
                        "session_id": row.get("session_id"),
                        "crime_type": row["crime_type"],
                        "created_at": row.get("created_at", ""),
                        "final_status": row.get("final_status"),
                        "final_score": row.get("final_score"),
                        "total_rounds": row.get("total_rounds"),
                        "grade": row.get("grade"),
                    }
            except Exception as e:
                logger.error("Supabase get_case_summary failed: %s – falling back to SQLite", e)
        return self._sqlite.get_case_summary(case_id)

    def list_cases(self, limit: int = 50, offset: int = 0, user_id: Optional[str] = None) -> List[Dict]:
        sb = self._sb_or_fallback()
        if sb:
            try:
                query = (
                    sb.table("verification_cases")
                    .select("*")
                    .order("created_at", desc=True)
                    .limit(limit)
                    .offset(offset)
                )
                if user_id:
                    query = query.eq("user_id", user_id)
                result = query.execute()
                return [
                    {
                        "case_id": r["case_id"],
                        "user_id": r.get("user_id"),
                        "source_case_id": r.get("source_case_id"),
                        "session_id": r.get("session_id"),
                        "crime_type": r["crime_type"],
                        "created_at": r.get("created_at", ""),
                        "final_status": r.get("final_status"),
                        "final_score": r.get("final_score"),
                        "total_rounds": r.get("total_rounds"),
                        "grade": r.get("grade"),
                    }
                    for r in result.data
                ]
            except Exception as e:
                logger.error("Supabase list_cases failed: %s – falling back to SQLite", e)
        return self._sqlite.list_cases(limit=limit, offset=offset, user_id=user_id)

    # ── round-level ops ──────────────────────────────────────────────────

    def save_round(
        self,
        case_id: str,
        round_num: int,
        attacker_data: Dict,
        judge_data: Dict,
        status: str,
        latency_ms: int,
        chat_message_id: Optional[str] = None,
    ) -> None:
        sb = self._sb_or_fallback()
        if sb:
            try:
                data = {
                    "case_id": case_id,
                    "round_num": round_num,
                    "attacker_prompt": attacker_data.get("prompt"),
                    "attacker_response": attacker_data.get("response"),
                    "attacker_challenges": attacker_data.get("challenges", []),
                    "judge_prompt": judge_data.get("prompt"),
                    "judge_response": judge_data.get("response"),
                    "judge_status": status,
                    "judge_articles_cited": judge_data.get("articles_cited", []),
                    "judge_claims_to_drop": judge_data.get("claims_to_drop", []),
                    "judge_confidence": judge_data.get("confidence"),
                    "latency_ms": latency_ms,
                }
                if chat_message_id:
                    data["chat_message_id"] = chat_message_id
                sb.table("verification_rounds").upsert(data, on_conflict="case_id,round_num").execute()
                logger.debug("Supabase: saved round %d for case %s", round_num, case_id)
            except Exception as e:
                logger.error("Supabase save_round failed: %s – falling back to SQLite", e)
        self._sqlite.save_round(case_id, round_num, attacker_data, judge_data, status, latency_ms, chat_message_id)

    def get_case_history(self, case_id: str) -> List[Dict]:
        sb = self._sb_or_fallback()
        if sb:
            try:
                result = (
                    sb.table("verification_rounds")
                    .select("*")
                    .eq("case_id", case_id)
                    .order("round_num")
                    .execute()
                )
                return [
                    {
                        "id": r.get("id"),
                        "case_id": r["case_id"],
                        "round_num": r["round_num"],
                        "timestamp": r.get("created_at", ""),
                        "attacker_prompt": r.get("attacker_prompt"),
                        "attacker_response": r.get("attacker_response"),
                        "attacker_challenges": json.dumps(r.get("attacker_challenges", []), ensure_ascii=False),
                        "judge_prompt": r.get("judge_prompt"),
                        "judge_response": r.get("judge_response"),
                        "judge_status": r.get("judge_status"),
                        "judge_articles_cited": json.dumps(r.get("judge_articles_cited", []), ensure_ascii=False),
                        "judge_claims_to_drop": json.dumps(r.get("judge_claims_to_drop", []), ensure_ascii=False),
                        "judge_confidence": r.get("judge_confidence"),
                        "latency_ms": r.get("latency_ms"),
                    }
                    for r in result.data
                ]
            except Exception as e:
                logger.error("Supabase get_case_history failed: %s – falling back to SQLite", e)
        return self._sqlite.get_case_history(case_id)

    def get_round(self, case_id: str, round_num: int) -> Optional[Dict]:
        sb = self._sb_or_fallback()
        if sb:
            try:
                result = (
                    sb.table("verification_rounds")
                    .select("*")
                    .eq("case_id", case_id)
                    .eq("round_num", round_num)
                    .execute()
                )
                if result.data:
                    r = result.data[0]
                    return {
                        "id": r.get("id"),
                        "case_id": r["case_id"],
                        "round_num": r["round_num"],
                        "timestamp": r.get("created_at", ""),
                        "attacker_prompt": r.get("attacker_prompt"),
                        "attacker_response": r.get("attacker_response"),
                        "attacker_challenges": json.dumps(r.get("attacker_challenges", []), ensure_ascii=False),
                        "judge_prompt": r.get("judge_prompt"),
                        "judge_response": r.get("judge_response"),
                        "judge_status": r.get("judge_status"),
                        "judge_articles_cited": json.dumps(r.get("judge_articles_cited", []), ensure_ascii=False),
                        "judge_claims_to_drop": json.dumps(r.get("judge_claims_to_drop", []), ensure_ascii=False),
                        "judge_confidence": r.get("judge_confidence"),
                        "latency_ms": r.get("latency_ms"),
                    }
            except Exception as e:
                logger.error("Supabase get_round failed: %s – falling back to SQLite", e)
        return self._sqlite.get_round(case_id, round_num)
