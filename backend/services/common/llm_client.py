import os
import json
import asyncio
from typing import Optional

import httpx
from pydantic import BaseModel, ValidationError

# Configuration from env
GROQ_URL = os.getenv("GROQ_API_URL", os.getenv("LLM_BASE_URL", ""))
GROQ_KEY = os.getenv("GROQ_API_KEY", os.getenv("GROQ_API_KEY", ""))
FALLBACK_URL = os.getenv("FALLBACK_API_URL", "")
FALLBACK_KEY = os.getenv("FALLBACK_API_KEY", "")
TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))


def _extract_content_from_response(j: dict) -> str:
    # OpenAI-compatible
    if isinstance(j, dict):
        if "choices" in j and isinstance(j["choices"], list):
            return j["choices"][0].get("message", {}).get("content", "")
        # Anthropic-style
        if "content" in j:
            if isinstance(j["content"], list) and len(j["content"]):
                return j["content"][0].get("text", "")
            return j["content"]
    return json.dumps(j)


async def _call_fallback(prompt: str, model: str, validator: Optional[BaseModel], max_tokens: int, temperature: float, reason: str) -> str:
    if not FALLBACK_URL or not FALLBACK_KEY:
        return f"LLM error and no fallback configured: {reason}"

    headers = {"Authorization": f"Bearer {FALLBACK_KEY}", "content-type": "application/json"}
    payload = {
        "model": model or os.getenv("FALLBACK_MODEL", ""),
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(FALLBACK_URL, headers=headers, json=payload, timeout=TIMEOUT)
            resp.raise_for_status()
            j = resp.json()
            content = _extract_content_from_response(j)
            if validator:
                try:
                    # validator may expect a dict or JSON string
                    validator.parse_raw(content if isinstance(content, str) else json.dumps(content))
                except ValidationError:
                    # Return raw content even if validation fails on fallback
                    pass
            return content
        except Exception as e:
            return f"Fallback LLM failed: {str(e)}"


async def llm_request(prompt: str, model: Optional[str] = None, validator: Optional[BaseModel] = None, max_tokens: int = 500, temperature: float = 0.3) -> str:
    """Async LLM request with GROQ primary and immediate fallback on rate-limiting.

    - Tries GROQ_URL first. On 429 or >=500 or network error, calls fallback endpoint.
    - If `validator` (pydantic model class) is provided, attempts to parse returned JSON and will trigger fallback when validation fails on primary.
    Returns the LLM content as a raw string (caller is responsible for JSON parsing if needed).
    """

    headers = {"Authorization": f"Bearer {GROQ_KEY}", "content-type": "application/json"}
    payload = {
        "model": model or os.getenv("LLM_MODEL", ""),
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(GROQ_URL, headers=headers, json=payload, timeout=TIMEOUT)
        except httpx.HTTPError as e:
            return await _call_fallback(prompt, model, validator, max_tokens, temperature, str(e))

        # Failover on rate limit or server errors
        if resp.status_code == 429:
            return await _call_fallback(prompt, model, validator, max_tokens, temperature, "rate_limited")
        if resp.status_code >= 500:
            return await _call_fallback(prompt, model, validator, max_tokens, temperature, f"server_error:{resp.status_code}")

        try:
            j = resp.json()
        except Exception as e:
            return await _call_fallback(prompt, model, validator, max_tokens, temperature, f"invalid_json:{str(e)}")

        content = _extract_content_from_response(j)

        # Validate returned JSON if validator provided
        if validator:
            try:
                validator.parse_raw(content if isinstance(content, str) else json.dumps(content))
            except ValidationError as ve:
                # Try fallback when validation fails
                return await _call_fallback(prompt, model, validator, max_tokens, temperature, f"validation_error:{ve}")

        return content


async def get_llm_status() -> dict:
    """Return current LLM connectivity health for primary and fallback endpoints."""
    status = {
        "groq": "unreachable" if not GROQ_URL else "unknown",
        "fallback": "not_configured" if not FALLBACK_URL else "unknown",
    }

    async with httpx.AsyncClient() as client:
        if GROQ_URL:
            try:
                resp = await client.get(GROQ_URL, timeout=5.0)
                status["groq"] = "healthy" if resp.status_code == 200 else f"unhealthy:{resp.status_code}"
            except Exception as e:
                status["groq"] = f"error:{str(e)}"

        if FALLBACK_URL:
            try:
                resp = await client.get(FALLBACK_URL, timeout=5.0)
                status["fallback"] = "healthy" if resp.status_code == 200 else f"unhealthy:{resp.status_code}"
            except Exception as e:
                status["fallback"] = f"error:{str(e)}"

    return status
