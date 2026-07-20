#!/usr/bin/env python3
"""
ACEB Evaluation Matrix
======================
End-to-end evaluation of the full pipeline through API endpoints.

Runs every test case through:
  1. Classification  (POST /api/classify)
  2. RAG Retrieval   (POST /api/retrieve)
  3. Verification    (POST /api/verify)

Compares results against expected output, builds a pass/fail matrix,
and STOPS on the first failure so the user can fix the code and re-run.

Usage:
  python scripts/evaluation_matrix.py [--base-url http://localhost:8000]
                                      [--email eval@test.com]
                                      [--password Eval@12345]
                                      [--continue-on-error]
"""
import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

# ── Constants ──────────────────────────────────────────────────────────────
TEST_CASES_DIR = Path(__file__).resolve().parent.parent / "data" / "test_cases" / "data"
DEFAULT_BASE_URL = os.getenv("EVAL_BASE_URL", "http://localhost:8000")
DEFAULT_EMAIL = os.getenv("EVAL_EMAIL", "evaluation@aceb.test")
DEFAULT_PASSWORD = os.getenv("EVAL_PASSWORD", "Eval@2026!!")
EVAL_USER_NAME = "Evaluation Matrix User"

# ── Evaluation Result Types ────────────────────────────────────────────────


class StageResult:
    """Result of a single evaluation stage for one test case."""

    def __init__(self, stage_name: str):
        self.stage_name = stage_name
        self.passed: bool = False
        self.status_code: Optional[int] = None
        self.response: Optional[dict] = None
        self.error: Optional[str] = None
        self.latency_ms: float = 0.0
        self.details: Dict[str, Any] = {}

    def to_dict(self) -> dict:
        return {
            "stage": self.stage_name,
            "passed": self.passed,
            "status_code": self.status_code,
            "error": self.error,
            "latency_ms": round(self.latency_ms, 2),
            "details": self.details,
        }


class TestCaseResult:
    """Complete evaluation result for one test case."""

    def __init__(self, test_case: dict):
        self.test_case = test_case
        self.case_id: str = test_case["case_id"]
        self.crime_type: str = test_case["crime_type"]
        self.difficulty: str = test_case.get("difficulty", "unknown")
        self.stages: Dict[str, StageResult] = {}
        self.overall_passed: bool = False
        self.notes: List[str] = []

    def add_stage(self, stage: StageResult):
        self.stages[stage.stage_name] = stage

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "crime_type": self.crime_type,
            "difficulty": self.difficulty,
            "overall_passed": self.overall_passed,
            "notes": self.notes,
            "stages": {k: v.to_dict() for k, v in self.stages.items()},
        }


# ── Main Evaluation Engine ─────────────────────────────────────────────────


class EvaluationMatrix:
    """Orchestrates the full evaluation pipeline."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        email: str = DEFAULT_EMAIL,
        password: str = DEFAULT_PASSWORD,
        continue_on_error: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.continue_on_error = continue_on_error
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.session_id: Optional[str] = None
        self.test_cases: List[dict] = []
        self.results: List[TestCaseResult] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.http = httpx.Client(timeout=60.0)

    # ── HTTP helpers ────────────────────────────────────────────────────

    def _headers(self) -> dict:
        if self.access_token:
            return {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "X-Tenant-ID": f"user_{self.user_id}" if self.user_id else "default",
            }
        return {"Content-Type": "application/json"}

    def refresh_access_token(self) -> bool:
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            return False
        status, data, err = self._request(
            "POST", "/api/auth/refresh",
            json={"refresh_token": self.refresh_token},
            _no_retry=True,
        )
        if status == 200 and data:
            self.access_token = data["access_token"]
            self.refresh_token = data.get("refresh_token", self.refresh_token)
            return True
        return False

    def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> Tuple[Optional[int], Optional[dict], Optional[str]]:
        """Make HTTP request, return (status_code, data, error).
        Auto-refreshes token on 401.
        """
        no_retry = kwargs.pop("_no_retry", False)

        for attempt in range(2):
            url = f"{self.base_url}{path}"
            headers = self._headers()
            if "headers" in kwargs:
                headers.update(kwargs.pop("headers"))
            try:
                resp = self.http.request(method, url, headers=headers, **kwargs)
                try:
                    data = resp.json()
                except Exception:
                    data = {"raw": resp.text}
                if resp.status_code == 401 and not no_retry and attempt == 0:
                    detail_str = str(data.get("detail", ""))
                    if "expired" in detail_str.lower() or "token" in detail_str.lower():
                        if self.refresh_access_token():
                            continue
                if resp.status_code >= 400:
                    detail = data.get("detail", data.get("message", resp.text))
                    return resp.status_code, data, str(detail)
                return resp.status_code, data, None
            except httpx.RequestError as e:
                return None, None, f"Request failed: {e}"
            except Exception as e:
                return None, None, f"Unexpected error: {e}"

        # Second attempt also failed
        return None, None, "Token refresh failed"

    # ── Auth ─────────────────────────────────────────────────────────────

    def register_user(self) -> bool:
        """Register the evaluation user (fails silently if already exists)."""
        status, data, err = self._request(
            "POST", "/api/auth/register",
            json={
                "email": self.email,
                "password": self.password,
                "full_name": EVAL_USER_NAME,
            },
        )
        if status == 201 and data:
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            self.user_id = data["user"]["id"]
            print(f"  ✓ User registered: {self.email} (id: {self.user_id})")
            return True
        if status == 409:
            print(f"  → User already exists, logging in...")
            return self.login_user()
        print(f"  ✗ Registration failed: {err}")
        return False

    def login_user(self) -> bool:
        """Login as the evaluation user."""
        status, data, err = self._request(
            "POST", "/api/auth/login",
            json={"email": self.email, "password": self.password},
        )
        if status == 200 and data:
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            self.user_id = data["user"]["id"]
            print(f"  ✓ Logged in: {self.email} (id: {self.user_id})")
            return True
        print(f"  ✗ Login failed: {err}")
        return False

    def verify_session(self) -> bool:
        """Verify session is active and get session_id."""
        status, data, err = self._request("POST", "/api/auth/verify")
        if status == 200 and data:
            self.session_id = data.get("session_id")
            return True
        print(f"  ✗ Session verification failed: {err}")
        return False

    # ── Test case loading ───────────────────────────────────────────────

    def load_test_cases(self) -> None:
        """Load all test case JSON files."""
        files = sorted(TEST_CASES_DIR.glob("TC_*.json"))
        if not files:
            print(f"  ✗ No test cases found in {TEST_CASES_DIR}")
            sys.exit(1)

        for f in files:
            with open(f, "r", encoding="utf-8") as fh:
                tc = json.load(fh)
                self.test_cases.append(tc)

        print(f"  ✓ Loaded {len(self.test_cases)} test cases from {len(files)} files")

    # ── Stage evaluation methods ────────────────────────────────────────

    def eval_classification(self, tc: dict) -> StageResult:
        """Test POST /api/classify - crime type classification."""
        stage = StageResult("classification")
        t0 = time.monotonic()

        evidence_texts = tc.get("evidence_texts", [])
        full_text = " ".join(b.get("text", "") for b in evidence_texts)

        status, data, err = self._request(
            "POST", "/api/classify",
            json={
                "text": full_text,
                "entities": {},
                "user_id": self.user_id,
                "session_id": self.session_id,
            },
        )
        stage.latency_ms = (time.monotonic() - t0) * 1000
        stage.status_code = status

        if err:
            stage.error = err
            return stage

        if not data:
            stage.error = "Empty response"
            return stage

        stage.response = data
        returned_type = data.get("crime_type", "").lower()
        expected_type = tc.get("expected_output", {}).get("crime_type", "").lower()

        # Accept alias mappings
        type_aliases = {
            "scam": "financial_fraud",
            "threat": "cyber_threat",
            "cyberthreat": "cyber_threat",
        }
        resolved_returned = type_aliases.get(returned_type, returned_type)
        resolved_expected = type_aliases.get(expected_type, expected_type)

        if resolved_returned == resolved_expected:
            stage.passed = True
            stage.details = {
                "expected_type": expected_type,
                "returned_type": returned_type,
                "confidence": data.get("confidence", 0),
            }
        else:
            stage.passed = False
            stage.details = {
                "expected_type": expected_type,
                "returned_type": returned_type,
                "returned_confidence": data.get("confidence", 0),
                "reasoning": data.get("reasoning", "")[:200],
            }
            stage.error = f"Type mismatch: expected '{expected_type}', got '{returned_type}'"

        return stage

    def eval_retrieval(self, tc: dict, classification: Optional[dict] = None) -> StageResult:
        """Test POST /api/retrieve - law article retrieval."""
        stage = StageResult("rag_retrieval")
        t0 = time.monotonic()

        evidence_texts = tc.get("evidence_texts", [])
        full_text = " ".join(b.get("text", "") for b in evidence_texts)
        expected_articles = tc.get("expected_output", {}).get("expected_articles", [])
        crime_type = tc.get("expected_output", {}).get("crime_type", "")

        status, data, err = self._request(
            "POST", "/api/retrieve",
            json={
                "query": full_text[:500],
                "crime_type": crime_type,
                "top_k": 5,
                "tenant_id": f"user_{self.user_id}" if self.user_id else "default",
                "transform_strategy": "auto",
                "user_id": self.user_id,
                "session_id": self.session_id,
            },
        )
        stage.latency_ms = (time.monotonic() - t0) * 1000
        stage.status_code = status

        if err:
            stage.error = err
            return stage

        if not data:
            stage.error = "Empty response"
            return stage

        stage.response = data
        articles = data.get("articles", [])

        if not articles:
            stage.error = "No articles retrieved"
            return stage

        # Check if any expected articles are in retrieved set
        retrieved_ids = []
        for a in articles:
            art = a.get("article_number", a.get("id", ""))
            law = a.get("law", "")
            # Normalize law: strip "Law " prefix and year suffix
            law_num = law.replace("Law ", "").split("/")[0].strip()
            retrieved_ids.append(f"law{law_num}_art{art}" if law_num else f"art{art}")

        if not expected_articles:
            stage.passed = True
            stage.details = {"retrieved_count": len(articles), "note": "No articles expected"}
            return stage

        matched = [ea for ea in expected_articles if any(ea in rid for rid in retrieved_ids)]
        match_ratio = len(matched) / len(expected_articles) if expected_articles else 1.0

        stage.details = {
            "expected_articles": expected_articles,
            "retrieved_ids": retrieved_ids,
            "matched": matched,
            "match_ratio": round(match_ratio, 2),
            "retrieved_count": len(articles),
        }

        if match_ratio >= 0.5:
            stage.passed = True
        else:
            stage.error = f"Low article match: {len(matched)}/{len(expected_articles)} expected found"
            stage.passed = False

        return stage

    def eval_verification(self, tc: dict, classification: Optional[dict] = None) -> StageResult:
        """Test POST /api/verify - multi-agent verification."""
        stage = StageResult("verification")
        t0 = time.monotonic()

        evidence_texts = tc.get("evidence_texts", [])
        full_text = " ".join(b.get("text", "") for b in evidence_texts)
        expected_articles = tc.get("expected_output", {}).get("expected_articles", [])
        expected_min_score = tc.get("expected_output", {}).get("expected_min_score", 50)
        crime_type = tc.get("expected_output", {}).get("crime_type", "")

        # Build evidence blocks
        blocks = []
        for b in evidence_texts:
            blocks.append({
                "block_id": b["block_id"],
                "text": b.get("text", ""),
                "expected_entities": b.get("expected_entities", {}),
            })

        # Build entities from all blocks
        all_entities: Dict[str, list] = {}
        for b in evidence_texts:
            for entity_type, values in b.get("expected_entities", {}).items():
                if entity_type not in all_entities:
                    all_entities[entity_type] = []
                for v in values:
                    if v not in all_entities[entity_type]:
                        all_entities[entity_type].append(v)

        status, data, err = self._request(
            "POST", "/api/verify",
            json={
                "evidence_text": full_text,
                "extracted_entities": all_entities,
                "classification": classification or {"crime_type": crime_type},
                "retrieved_articles": [{"article_number": a} for a in expected_articles],
                "evidence_blocks": blocks,
                "case_id": f"eval-{tc['case_id']}",
                "session_id": self.session_id,
            },
        )
        stage.latency_ms = (time.monotonic() - t0) * 1000
        stage.status_code = status

        if err:
            stage.error = err
            return stage

        if not data:
            stage.error = "Empty response"
            return stage

        stage.response = data
        final_score = data.get("final_score", 0)
        grade = data.get("grade", "WEAK")
        verification_status = data.get("status", "")

        stage.details = {
            "final_score": final_score,
            "grade": grade,
            "verification_status": verification_status,
            "rounds": data.get("rounds", 0),
            "expected_min_score": expected_min_score,
        }

        if final_score >= expected_min_score:
            stage.passed = True
        else:
            stage.error = (
                f"Score {final_score} < expected min {expected_min_score} "
                f"(grade: {grade}, status: {verification_status})"
            )
            stage.passed = False

        return stage

    # ── Run evaluation ──────────────────────────────────────────────────

    def run(self) -> bool:
        """Run the complete evaluation. Returns True if all passed."""
        self.start_time = datetime.now(timezone.utc)

        print(f"\n{'='*70}")
        print(f"  ACEB EVALUATION MATRIX")
        print(f"{'='*70}")
        print(f"  Base URL:    {self.base_url}")
        print(f"  Test cases:  {len(self.test_cases)}")
        print(f"  Continue:    {'yes' if self.continue_on_error else 'NO (stop on first failure)'}")
        print(f"{'='*70}\n")

        total = len(self.test_cases)
        passed_total = 0
        failed_total = 0

        for idx, tc in enumerate(self.test_cases, 1):
            case_id = tc["case_id"]
            crime_type = tc["crime_type"]
            difficulty = tc.get("difficulty", "?")
            expected = tc.get("expected_output", {}).get("crime_type", "?")

            print(f"\n[{idx:3d}/{total}] {case_id} | {crime_type:20s} | {difficulty:6s} | → {expected}")
            print(f"  {'─'*60}")

            result = TestCaseResult(tc)

            # Stage 1: Classification
            cls_result = self.eval_classification(tc)
            result.add_stage(cls_result)
            icon = "✓" if cls_result.passed else "✗"
            lat = f"{cls_result.latency_ms:.0f}ms"
            print(f"  {icon} Classify: {cls_result.details.get('returned_type', '?')} (conf: {cls_result.details.get('confidence', 0):.2f}) [{lat}]")
            if cls_result.error:
                print(f"    └─ {cls_result.error}")

            if not cls_result.passed and not self.continue_on_error:
                self._fail_fast(result, "classification stage failed")
                return False

            # Stage 2: RAG Retrieval
            rag_result = self.eval_retrieval(tc, cls_result.response)
            result.add_stage(rag_result)
            icon = "✓" if rag_result.passed else "✗"
            lat = f"{rag_result.latency_ms:.0f}ms"
            details = rag_result.details
            matched = details.get("matched", [])
            exp_count = len(details.get("expected_articles", []))
            print(f"  {icon} RAG:      {len(matched)}/{exp_count} articles matched [{lat}]")
            if rag_result.error:
                print(f"    └─ {rag_result.error}")

            if not rag_result.passed and not self.continue_on_error:
                self._fail_fast(result, "RAG retrieval stage failed")
                return False

            # Stage 3: Verification
            ver_result = self.eval_verification(tc, cls_result.response)
            result.add_stage(ver_result)
            icon = "✓" if ver_result.passed else "✗"
            lat = f"{ver_result.latency_ms:.0f}ms"
            details = ver_result.details
            exp_min = details.get("expected_min_score", 0)
            actual_score = details.get("final_score", 0)
            grade = details.get("grade", "?")
            print(f"  {icon} Verify:   score={actual_score} (min={exp_min}) grade={grade} rounds={details.get('rounds', 0)} [{lat}]")
            if ver_result.error:
                print(f"    └─ {ver_result.error}")

            if not ver_result.passed and not self.continue_on_error:
                self._fail_fast(result, "verification stage failed")
                return False

            # Overall status
            all_passed = all(s.passed for s in result.stages.values())
            result.overall_passed = all_passed
            self.results.append(result)

            if all_passed:
                passed_total += 1
                print(f"  ★ PASS")
            else:
                failed_total += 1
                print(f"  ✗ FAIL")
                failed_stages = [s for s in result.stages.values() if not s.passed]
                for s in failed_stages:
                    result.notes.append(f"{s.stage_name}: {s.error}")
                if not self.continue_on_error:
                    return False

        self.end_time = datetime.now(timezone.utc)
        self._print_summary()

        return failed_total == 0

    def _fail_fast(self, result: TestCaseResult, reason: str) -> None:
        """Stop immediately on failure."""
        self.results.append(result)
        self.end_time = datetime.now(timezone.utc)
        print(f"\n  ⛔ STOP: {reason}")
        print(f"  Fix the issue and re-run the evaluation.")
        self._print_summary()

    def _print_summary(self) -> None:
        """Print the final evaluation summary/matrix."""
        elapsed = (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0

        total = len(self.results)
        passed = sum(1 for r in self.results if r.overall_passed)
        failed = total - passed

        print(f"\n{'='*70}")
        print(f"  EVALUATION MATRIX SUMMARY")
        print(f"{'='*70}")

        # Per-crime-type breakdown
        by_type: Dict[str, Dict] = {}
        for r in self.results:
            ct = r.test_case.get("expected_output", {}).get("crime_type", r.crime_type)
            if ct not in by_type:
                by_type[ct] = {"total": 0, "passed": 0, "failed": 0}
            by_type[ct]["total"] += 1
            if r.overall_passed:
                by_type[ct]["passed"] += 1
            else:
                by_type[ct]["failed"] += 1

        print(f"\n  {'Crime Type':25s} {'Total':>6s} {'Passed':>6s} {'Failed':>6s} {'Rate':>6s}")
        print(f"  {'─'*49}")
        for ct, counts in sorted(by_type.items()):
            rate = (counts["passed"] / counts["total"] * 100) if counts["total"] else 0
            print(f"  {ct:25s} {counts['total']:6d} {counts['passed']:6d} {counts['failed']:6d} {rate:5.0f}%")

        print(f"  {'─'*49}")
        overall_rate = (passed / total * 100) if total else 0
        print(f"  {'TOTAL':25s} {total:6d} {passed:6d} {failed:6d} {overall_rate:5.0f}%")
        print(f"\n  Elapsed: {elapsed:.1f}s")

        # Detailed matrix table
        print(f"\n{'='*70}")
        print(f"  DETAILED MATRIX")
        print(f"{'='*70}")
        print(f"  {'Case ID':22s} {'Type':18s} {'Cls':4s} {'RAG':4s} {'Ver':4s} {'Status':8s}")
        print(f"  {'─'*60}")
        for r in self.results:
            cls_p = r.stages.get("classification", StageResult("")).passed
            rag_p = r.stages.get("rag_retrieval", StageResult("")).passed
            ver_p = r.stages.get("verification", StageResult("")).passed
            ct = r.test_case.get("expected_output", {}).get("crime_type", r.crime_type)
            status = "PASS" if r.overall_passed else "FAIL"
            print(f"  {r.case_id:22s} {ct:18s} {'✓' if cls_p else '✗':4s} {'✓' if rag_p else '✗':4s} {'✓' if ver_p else '✗':4s} {status:8s}")

        # Failed cases details
        failed_results = [r for r in self.results if not r.overall_passed]
        if failed_results:
            print(f"\n{'='*70}")
            print(f"  FAILED CASES")
            print(f"{'='*70}")
            for r in failed_results:
                print(f"  • {r.case_id} ({r.crime_type}):")
                for note in r.notes:
                    print(f"    └─ {note}")

        print(f"\n{'='*70}")
        if failed == 0:
            print(f"  ✓ ALL {total} TEST CASES PASSED")
        else:
            print(f"  ✗ {failed}/{total} TEST CASES FAILED")
        print(f"{'='*70}")

    def save_results(self, path: Optional[str] = None) -> str:
        """Save results to JSON file."""
        if not path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = f"evaluation_matrix_{timestamp}.json"

        output = {
            "summary": {
                "base_url": self.base_url,
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r.overall_passed),
                "failed": sum(1 for r in self.results if not r.overall_passed),
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
            },
            "results": [r.to_dict() for r in self.results],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n  Results saved to: {path}")
        return path


# ── CLI Entry Point ────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="ACEB Evaluation Matrix")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Evaluation user email")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Evaluation user password")
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue running even if tests fail (default: stop on first failure)",
    )
    parser.add_argument("--output", help="Path to save results JSON")
    parser.add_argument("--register", action="store_true", help="Force register new user")
    args = parser.parse_args()

    eval_matrix = EvaluationMatrix(
        base_url=args.base_url,
        email=args.email,
        password=args.password,
        continue_on_error=args.continue_on_error,
    )

    # Phase 1: Register/Login
    print(f"\n{'─'*60}")
    print("  PHASE 1: Authentication")
    print(f"{'─'*60}")
    if args.register:
        if not eval_matrix.register_user():
            print("  Trying login as fallback...")
            if not eval_matrix.login_user():
                sys.exit(1)
    else:
        if not eval_matrix.login_user():
            print("  Trying to register...")
            if not eval_matrix.register_user():
                sys.exit(1)

    if not eval_matrix.verify_session():
        sys.exit(1)

    # Phase 2: Load test cases
    print(f"\n{'─'*60}")
    print("  PHASE 2: Load Test Cases")
    print(f"{'─'*60}")
    eval_matrix.load_test_cases()

    # Phase 3: Run evaluation
    print(f"\n{'─'*60}")
    print("  PHASE 3: Run Evaluation")
    print(f"{'─'*60}")
    all_passed = eval_matrix.run()

    # Phase 4: Save results
    print(f"\n{'─'*60}")
    print("  PHASE 4: Save Results")
    print(f"{'─'*60}")
    eval_matrix.save_results(args.output)

    # Exit code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
