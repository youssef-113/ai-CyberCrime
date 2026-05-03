"""Verification Persistence & Audit Trail – SQLite-backed store."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional


class VerificationStore:
    """Persist every verification round for debugging and legal audit."""

    DEFAULT_DB_PATH = "data/verification.db"

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_db()

    # ── connection helper ─────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ── schema ────────────────────────────────────────────────────────────

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS verification_cases (
                    case_id       TEXT PRIMARY KEY,
                    crime_type    TEXT NOT NULL,
                    created_at    TEXT NOT NULL,
                    final_status  TEXT,
                    final_score   INTEGER,
                    total_rounds  INTEGER,
                    grade         TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS verification_rounds (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id             TEXT    NOT NULL,
                    round_num           INTEGER NOT NULL,
                    timestamp           TEXT    NOT NULL,
                    attacker_prompt     TEXT,
                    attacker_response   TEXT,
                    attacker_challenges TEXT,
                    judge_prompt        TEXT,
                    judge_response      TEXT,
                    judge_status        TEXT,
                    judge_articles_cited TEXT,
                    judge_claims_to_drop TEXT,
                    judge_confidence    REAL,
                    latency_ms          INTEGER,
                    UNIQUE(case_id, round_num),
                    FOREIGN KEY (case_id) REFERENCES verification_cases(case_id)
                )
            """)
            conn.commit()

    # ── case-level ops ────────────────────────────────────────────────────

    def create_case(self, case_id: str, crime_type: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO verification_cases (case_id, crime_type, created_at) "
                "VALUES (?, ?, ?)",
                (case_id, crime_type, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def update_case_status(
        self,
        case_id: str,
        final_status: str,
        final_score: int,
        total_rounds: int,
        grade: str,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE verification_cases "
                "SET final_status=?, final_score=?, total_rounds=?, grade=? "
                "WHERE case_id=?",
                (final_status, final_score, total_rounds, grade, case_id),
            )
            conn.commit()

    def get_case_summary(self, case_id: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM verification_cases WHERE case_id=?", (case_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_cases(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM verification_cases "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── round-level ops ──────────────────────────────────────────────────

    def save_round(
        self,
        case_id: str,
        round_num: int,
        attacker_data: Dict,
        judge_data: Dict,
        status: str,
        latency_ms: int,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO verification_rounds
                    (case_id, round_num, timestamp,
                     attacker_prompt, attacker_response, attacker_challenges,
                     judge_prompt, judge_response, judge_status,
                     judge_articles_cited, judge_claims_to_drop, judge_confidence,
                     latency_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_id,
                    round_num,
                    datetime.now(timezone.utc).isoformat(),
                    attacker_data.get("prompt"),
                    attacker_data.get("response"),
                    json.dumps(attacker_data.get("challenges", []), ensure_ascii=False),
                    judge_data.get("prompt"),
                    judge_data.get("response"),
                    status,
                    json.dumps(judge_data.get("articles_cited", []), ensure_ascii=False),
                    json.dumps(judge_data.get("claims_to_drop", []), ensure_ascii=False),
                    judge_data.get("confidence"),
                    latency_ms,
                ),
            )
            conn.commit()

    def get_case_history(self, case_id: str) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM verification_rounds "
                "WHERE case_id=? ORDER BY round_num",
                (case_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── convenience ──────────────────────────────────────────────────────

    def get_round(self, case_id: str, round_num: int) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM verification_rounds "
                "WHERE case_id=? AND round_num=?",
                (case_id, round_num),
            ).fetchone()
            return dict(row) if row else None
