"""Query Transformation - HyDE, RAG-Fusion, Step-Back Prompting

Query transformation solves many retrieval issues:
- HyDE: works well for short queries
- RAG-Fusion: generates multiple query variations and merges results
- Step-back prompting: helps with complex, multi-step questions

LLM Provider: Ollama (local) by default, falls back to Groq if configured.
"""
import logging
from typing import List, Dict, Optional

import httpx

from .config import config

logger = logging.getLogger("rag.query_transform")


async def _call_ollama(prompt: str, system: str = "", max_tokens: int = 300) -> str:
    """Call Ollama API for query transformation."""
    base_url = config.ollama.base_url.rstrip("/")
    model = config.ollama.model

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "system": system or "You are a legal research assistant specializing in Egyptian cybercrime law. Be concise.",
                    "stream": False,
                    "options": {
                        "temperature": config.ollama.temperature,
                        "num_predict": max_tokens,
                    },
                },
                timeout=config.ollama.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", prompt).strip()
    except Exception as e:
        logger.warning(f"Ollama call failed: {e}")
        return ""


async def _call_groq(prompt: str, system: str = "", max_tokens: int = 300) -> str:
    """Call Groq API as fallback LLM."""
    from services.common.llm_client import llm_request
    
    try:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        result = await llm_request(
            prompt=full_prompt,
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return result if result else ""
    except Exception as e:
        logger.warning(f"Groq call failed: {e}")
        return ""


async def _call_llm(prompt: str, system: str = "", max_tokens: int = 300) -> str:
    """Call LLM for query transformation. Tries Ollama first, then Groq."""
    provider = config.query_transform.llm_provider

    if provider == "ollama":
        result = await _call_ollama(prompt, system, max_tokens)
        if result:
            return result
        # Fall through to Groq if Ollama fails
        logger.info("Ollama failed, trying Groq fallback")

    if provider in ("groq", "ollama"):
        result = await _call_groq(prompt, system, max_tokens)
        if result:
            return result

    logger.warning("All LLM providers failed for query transform")
    return prompt


async def hyde_transform(query: str) -> str:
    """HyDE (Hypothetical Document Embeddings).

    Generate a hypothetical answer to the query, then use that
    answer's embedding for retrieval. Works well for short queries.
    """
    if not config.query_transform.hyde_enabled:
        return query

    prompt = f"""Given this legal query about Egyptian cybercrime law, write a hypothetical detailed answer paragraph that would be the ideal retrieval result. The answer should use legal terminology and reference specific law articles where possible.

Query: {query}

Hypothetical answer:"""

    result = await _call_llm(prompt, max_tokens=200)
    logger.debug(f"HyDE transform: '{query[:50]}' -> '{result[:50]}'")
    return result


async def rag_fusion_transform(query: str) -> List[str]:
    """RAG-Fusion: Generate multiple query variations.

    Creates N different phrasings of the same query,
    retrieves for each, and merges results.
    """
    if not config.query_transform.rag_fusion_enabled:
        return [query]

    n = config.query_transform.rag_fusion_queries

    prompt = f"""Generate {n} different search queries that all seek the same legal information as the original query. Each variation should use different legal terminology and phrasing. Return ONLY the queries, one per line, numbered.

Original query: {query}

Variations:"""

    result = await _call_llm(prompt, max_tokens=300)

    # Parse numbered list
    variations = []
    for line in result.split("\n"):
        line = line.strip()
        # Remove numbering like "1. ", "1) "
        if line and len(line) > 3:
            cleaned = line.lstrip("0123456789.-) ")
            if cleaned:
                variations.append(cleaned)

    # Always include original query
    all_queries = [query] + variations[:n]
    logger.debug(f"RAG-Fusion: generated {len(all_queries)} query variations")
    return all_queries


async def step_back_transform(query: str) -> str:
    """Step-back prompting for complex, multi-step questions.

    Generates a broader, more general version of the query
    to retrieve relevant background context.
    """
    if not config.query_transform.step_back_enabled:
        return query

    prompt = f"""Given this specific legal query, generate a broader, more general question about the underlying legal concept or principle. This helps retrieve relevant background context.

Specific query: {query}

Broader question:"""

    result = await _call_llm(prompt, max_tokens=150)
    logger.debug(f"Step-back: '{query[:50]}' -> '{result[:50]}'")
    return result


async def transform_query(query: str, strategy: str = "auto") -> Dict:
    """Apply query transformation based on strategy.

    Args:
        query: Original user query
        strategy: "hyde" | "fusion" | "step_back" | "auto"

    Returns:
        Dict with transformed queries and metadata
    """
    if strategy == "auto":
        # Auto-select based on query characteristics
        word_count = len(query.split())
        if word_count <= 5:
            strategy = "hyde"  # Short queries benefit from HyDE
        elif "?" in query and word_count > 15:
            strategy = "step_back"  # Complex questions benefit from step-back
        else:
            strategy = "fusion"  # Default to RAG-Fusion

    result = {"original_query": query, "strategy": strategy, "queries": [query]}

    try:
        if strategy == "hyde":
            transformed = await hyde_transform(query)
            result["queries"] = [transformed]
            result["hyde_document"] = transformed

        elif strategy == "fusion":
            variations = await rag_fusion_transform(query)
            result["queries"] = variations

        elif strategy == "step_back":
            broader = await step_back_transform(query)
            result["queries"] = [query, broader]
            result["step_back_query"] = broader

    except Exception as e:
        logger.error(f"Query transformation failed: {e}")
        result["queries"] = [query]
        result["error"] = str(e)

    return result
