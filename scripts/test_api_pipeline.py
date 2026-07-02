#!/usr/bin/env python3
import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional, Tuple

import requests

BASE_URL = os.getenv("BASE_URL", "https://cyber-crime-production.up.railway.app").rstrip("/")
EMAIL = os.getenv("TEST_EMAIL", "test@example.com")
PASSWORD = os.getenv("TEST_PASSWORD", "Test123456!")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "15"))

AUTH_TOKEN: Optional[str] = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test the Railway API suite")
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--email", default=EMAIL)
    parser.add_argument("--password", default=PASSWORD)
    parser.add_argument("--token", default=os.getenv("API_TOKEN"))
    parser.add_argument("--skip-auth", action="store_true")
    parser.add_argument("--timeout", type=int, default=REQUEST_TIMEOUT)
    return parser.parse_args()


def print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def request(method: str, path: str, timeout: int, **kwargs) -> requests.Response:
    url = f"{BASE_URL}{path}"
    headers = kwargs.pop("headers", {})
    if AUTH_TOKEN:
        headers.setdefault("Authorization", f"Bearer {AUTH_TOKEN}")
    if "json" in kwargs:
        headers.setdefault("Content-Type", "application/json")
    try:
        resp = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
        return resp
    except requests.Timeout:
        print(f"[ERR] {method} {path} -> timed out after {timeout}s")
        return requests.Response()
    except Exception as exc:
        print(f"[ERR] {method} {path} -> request failed: {exc}")
        return requests.Response()


def show_result(label: str, resp: requests.Response, expected_statuses: Any = (200,)) -> Tuple[bool, Any]:
    if isinstance(expected_statuses, int):
        expected_statuses = (expected_statuses,)
    ok = resp.status_code in expected_statuses
    print(f"[{resp.status_code}] {label}")
    try:
        body = resp.json()
    except Exception:
        body = resp.text[:1000]
    if isinstance(body, (dict, list)):
        print(json.dumps(body, indent=2)[:2500])
    else:
        print(body)
    print()
    return ok, body


def auth_flow(email: str, password: str, skip_auth: bool) -> bool:
    print_section("Auth")
    global AUTH_TOKEN

    if skip_auth:
        print("Skipping auth flow because --skip-auth was supplied")
        return True

    register_payload = {"email": email, "password": password}
    resp = request("POST", "/api/auth/register", timeout=REQUEST_TIMEOUT, json=register_payload)
    ok, _ = show_result("POST /api/auth/register", resp, (200, 201))
    if not ok and resp.status_code not in {400, 409}:
        return False

    login_payload = {"email": email, "password": password}
    resp = request("POST", "/api/auth/login", timeout=REQUEST_TIMEOUT, json=login_payload)
    ok, body = show_result("POST /api/auth/login", resp, (200, 201))
    if not ok:
        return False

    token = body.get("access_token") or body.get("token") or body.get("accessToken")
    if not token:
        print("No access token returned from login")
        return False

    AUTH_TOKEN = token
    return True


def health_checks(timeout: int) -> None:
    print_section("Health")
    endpoints = [
        "/api/health",
        "/api/health/aggregate",
        "/api/ready",
        "/api/metrics",
        "/ocr/health",
        "/classifier/health",
        "/rag/health",
        "/verification/health",
        "/pdf/health",
    ]
    for path in endpoints:
        resp = request("GET", path, timeout=timeout)
        show_result(f"GET {path}", resp, 200)


def auth_protected_checks(timeout: int) -> None:
    print_section("Protected auth checks")
    endpoints = [
        "/api/auth/me",
        "/api/auth/verify",
        "/api/auth/usersList",
    ]
    for path in endpoints:
        resp = request("GET", path, timeout=timeout)
        show_result(f"GET {path}", resp, 200)


def session_and_chat_checks(timeout: int) -> None:
    print_section("Sessions and chat")
    resp = request("POST", "/api/sessions", timeout=timeout, json={"user_id": EMAIL})
    show_result("POST /api/sessions", resp, 200)

    resp = request("GET", "/api/sessions/list", timeout=timeout)
    show_result("GET /api/sessions/list", resp, 200)

    resp = request("POST", "/api/chat", timeout=timeout, json={"message": "hello", "user_id": EMAIL})
    show_result("POST /api/chat", resp, 200)

    resp = request("GET", "/api/chat/history", timeout=timeout)
    show_result("GET /api/chat/history", resp, 200)


def pipeline_smoke_test(timeout: int) -> None:
    print_section("Pipeline smoke test")
    sample_path = Path("/tmp/test_evidence.png")
    if not sample_path.exists():
        # create a tiny placeholder PNG bytes
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAIAAeIhvAAAAAElFTkSuQmCC"
        )
        sample_path.write_bytes(png_bytes)

    with sample_path.open("rb") as fh:
        files = {"files": (sample_path.name, fh, "image/png")}
        resp = request("POST", "/api/analyze", timeout=timeout, files=files)
        show_result("POST /api/analyze", resp, (200, 201, 202))

    if resp.ok:
        body = resp.json()
        case_id = body.get("case_id")
        if case_id:
            time.sleep(3)
            resp2 = request("GET", f"/api/cases/{case_id}", timeout=timeout)
            show_result(f"GET /api/cases/{case_id}", resp2, (200, 201, 202))

            resp3 = request("GET", f"/api/pdf/{case_id}", timeout=timeout)
            print(f"[{'200' if resp3.ok else resp3.status_code}] GET /api/pdf/{case_id}")
            print(resp3.text[:500])
            print()


def misc_endpoints(timeout: int) -> None:
    print_section("Misc endpoints")
    checks = [
        ("POST", "/api/ocr/extract"),
        ("POST", "/api/ocr/extract/batch"),
        ("GET", "/api/ocr/engines/status"),
        ("POST", "/api/retrieve"),
        ("POST", "/api/classify"),
        ("GET", "/api/stats"),
        ("GET", "/api/tenants"),
        ("POST", "/api/verify"),
    ]
    for method, path in checks:
        resp = request(method, path, timeout=timeout)
        show_result(f"{method} {path}", resp, (200, 201, 202, 400, 422))


def main() -> None:
    args = parse_args()
    global BASE_URL, EMAIL, PASSWORD, REQUEST_TIMEOUT, AUTH_TOKEN
    BASE_URL = args.base_url.rstrip("/")
    EMAIL = args.email
    PASSWORD = args.password
    REQUEST_TIMEOUT = args.timeout
    print(f"Testing {BASE_URL}")

    if not auth_flow(EMAIL, PASSWORD, args.skip_auth):
        print("Auth flow failed. Set TEST_EMAIL/TEST_PASSWORD or pass --token.")
        sys.exit(1)

    health_checks(REQUEST_TIMEOUT)
    auth_protected_checks(REQUEST_TIMEOUT)
    session_and_chat_checks(REQUEST_TIMEOUT)
    pipeline_smoke_test(REQUEST_TIMEOUT)
    misc_endpoints(REQUEST_TIMEOUT)


if __name__ == "__main__":
    main()
