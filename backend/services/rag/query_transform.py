"""Query Transformation - HyDE, RAG-Fusion, Step-Back Prompting.

Query transformation helps improve retrieval quality:
- HyDE: useful for short or underspecified queries.
- RAG-Fusion: generates multiple query variations and merges results.
- Step-back prompting: broadens complex questions to retrieve background context.

LLM provider:
- Ollama is used by default.
- Groq can be used directly or as a fallback when configured.
"""

import logging
import re
from typing import Any, Dict, List

import httpx

from .config import config

logger = logging.getLogger("rag.query_transform")


async def _call_ollama(
    prompt: str,
    system: str = "",
    max_tokens: int = 300,
) -> str:
    """Call the Ollama API for query transformation."""
    base_url = config.ollama.base_url.rstrip("/")
    model = config.ollama.model

    timeout = httpx.Timeout(
        timeout=config.ollama.timeout,
        connect=min(config.ollama.timeout, 5.0),
    )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "system": (
                        system
                        or (
                            "You are a legal research assistant specializing "
                            "in Egyptian cybercrime law. Be concise and do not "
                            "invent legal citations, article numbers, cases, "
                            "or penalties."
                        )
                    ),
                    "stream": False,
                    "options": {
                        "temperature": config.ollama.temperature,
                        "num_predict": max_tokens,
                    },
                },
            )

            response.raise_for_status()
            data = response.json()

            generated_text = data.get("response", "")
            if not isinstance(generated_text, str):
                logger.warning(
                    "Ollama returned a non-string response"
                )
                return ""

            return generated_text.strip()

    except Exception as exc:
        logger.warning(
            "Ollama query-transform call failed: %s",
            exc,
        )
        return ""


async def _call_groq(
    prompt: str,
    system: str = "",
    max_tokens: int = 300,
) -> str:
    """Call Groq as the fallback query-transformation LLM.

    Timeout handling should preferably be implemented inside the shared
    llm_request client so that all Groq calls use the same timeout policy.
    """
    try:
        from services.common.llm_client import llm_request

        full_prompt = (
            f"{system}\n\n{prompt}"
            if system
            else prompt
        )

        result = await llm_request(
            prompt=full_prompt,
            max_tokens=max_tokens,
            temperature=0.3,
        )

        if not isinstance(result, str):
            if result is not None:
                logger.warning(
                    "Groq returned a non-string response"
                )
            return ""

        return result.strip()

    except Exception as exc:
        logger.warning(
            "Groq query-transform call failed: %s",
            exc,
        )
        return ""


async def _call_llm(
    prompt: str,
    system: str = "",
    max_tokens: int = 300,
) -> str:
    """Call the configured LLM and return an empty string on failure.

    Returning an empty string is intentional. Each transformation strategy
    is responsible for selecting its own safe fallback, usually the original
    user query. Returning the prompt itself would pollute retrieval.
    """
    provider = str(
        config.query_transform.llm_provider
    ).strip().lower()

    if provider == "ollama":
        result = await _call_ollama(
            prompt=prompt,
            system=system,
            max_tokens=max_tokens,
        )

        if result:
            return result

        logger.info(
            "Ollama failed; attempting Groq fallback"
        )

        result = await _call_groq(
            prompt=prompt,
            system=system,
            max_tokens=max_tokens,
        )

        if result:
            return result

    elif provider == "groq":
        result = await _call_groq(
            prompt=prompt,
            system=system,
            max_tokens=max_tokens,
        )

        if result:
            return result

    else:
        logger.warning(
            "Unsupported query-transform LLM provider: %s",
            provider,
        )

    logger.warning(
        "All LLM providers failed for query transformation"
    )
    return ""


def _deduplicate_queries(
    queries: List[str],
) -> List[str]:
    """Remove empty and duplicate queries while preserving order."""
    unique_queries: List[str] = []
    seen = set()

    for query in queries:
        if not isinstance(query, str):
            continue

        cleaned = query.strip()
        if not cleaned:
            continue

        normalized = " ".join(cleaned.split()).casefold()

        if normalized in seen:
            continue

        seen.add(normalized)
        unique_queries.append(cleaned)

    return unique_queries


def _parse_fusion_variations(
    response_text: str,
    requested_count: int,
) -> List[str]:
    """Parse query variations returned by the LLM."""
    if not response_text:
        return []

    variations: List[str] = []

    for line in response_text.splitlines():
        cleaned = re.sub(
            r"^\s*(?:[-*•]\s*)?(?:\d+\s*[\.\)\-:]\s*)?",
            "",
            line,
        ).strip()

        if not cleaned:
            continue

        lowered = cleaned.casefold()

        if lowered in {
            "variations",
            "variations:",
            "queries",
            "queries:",
        }:
            continue

        variations.append(cleaned)

    variations = _deduplicate_queries(variations)

    return variations[:max(requested_count, 0)]


async def hyde_transform(query: str) -> str:
    """Generate a hypothetical retrieval passage for HyDE.

    If generation fails, the original query is returned.
    """
    if not config.query_transform.hyde_enabled:
        return query

    prompt = f"""Write a hypothetical legal passage that would likely contain
the answer to the following query about Egyptian cybercrime law.

Use relevant legal terminology and concepts, but do not invent article
numbers, court decisions, penalties, citations, dates, or factual claims
that are not present in the query.

Query:
{query}

Hypothetical retrieval passage:"""

    transformed = await _call_llm(
        prompt=prompt,
        max_tokens=200,
    )

    if not transformed:
        logger.warning(
            "HyDE generation failed; using original query"
        )
        return query

    logger.debug(
        "HyDE transform: %r -> %r",
        query[:50],
        transformed[:50],
    )

    return transformed


async def rag_fusion_transform(
    query: str,
) -> List[str]:
    """Generate multiple query variations for RAG-Fusion.

    The original query is always retained. If generation or parsing fails,
    only the original query is returned.
    """
    if not config.query_transform.rag_fusion_enabled:
        return [query]

    requested_count = max(
        int(config.query_transform.rag_fusion_queries),
        0,
    )

    if requested_count == 0:
        return [query]

    prompt = f"""Generate {requested_count} different search queries that seek
the same legal information as the original query.

Requirements:
- Use different legal terminology and phrasing.
- Preserve the original legal intent.
- Do not answer the question.
- Do not invent article numbers, case names, penalties, or facts.
- Return only one query per line.
- Numbering is optional.

Original query:
{query}

Query variations:"""

    response_text = await _call_llm(
        prompt=prompt,
        max_tokens=300,
    )

    if not response_text:
        logger.warning(
            "RAG-Fusion generation failed; using original query only"
        )
        return [query]

    variations = _parse_fusion_variations(
        response_text=response_text,
        requested_count=requested_count,
    )

    logger.debug(
        "RAG-Fusion requested %d variations and parsed %d",
        requested_count,
        len(variations),
    )

    if not variations:
        logger.warning(
            "RAG-Fusion returned no valid variations; "
            "using original query only"
        )
        return [query]

    all_queries = _deduplicate_queries(
        [query, *variations]
    )

    logger.debug(
        "RAG-Fusion produced %d total queries",
        len(all_queries),
    )

    return all_queries


async def step_back_transform(
    query: str,
) -> str:
    """Generate a broader question for step-back retrieval.

    If generation fails, the original query is returned.
    """
    if not config.query_transform.step_back_enabled:
        return query

    prompt = f"""Generate a broader legal research question about the
underlying legal principle in the specific query below.

Requirements:
- Preserve the original topic.
- Make the question broader, not unrelated.
- Do not answer the question.
- Do not invent article numbers, cases, penalties, or facts.
- Return only the broader question.

Specific query:
{query}

Broader question:"""

    broader_query = await _call_llm(
        prompt=prompt,
        max_tokens=150,
    )

    if not broader_query:
        logger.warning(
            "Step-back generation failed; using original query"
        )
        return query

    logger.debug(
        "Step-back transform: %r -> %r",
        query[:50],
        broader_query[:50],
    )

    return broader_query


async def transform_query(
    query: str,
    strategy: str = "auto",
) -> Dict[str, Any]:
    """Apply a query-transformation strategy.

    Args:
        query: Original user query.
        strategy: ``hyde``, ``fusion``, ``step_back``, ``none``, or ``auto``.

    Returns:
        A dictionary containing the original query, selected strategy,
        transformed queries, and optional strategy-specific metadata.

        For HyDE:
        - ``queries`` contains only the original query.
        - ``hyde_document`` contains the hypothetical passage and should be
          used separately for vector retrieval.
    """
    cleaned_query = query.strip()

    if not cleaned_query:
        return {
            "original_query": query,
            "strategy": "none",
            "queries": [],
            "error": "Query is empty",
        }

    selected_strategy = str(strategy).strip().lower()

    valid_strategies = {
        "auto",
        "none",
        "hyde",
        "fusion",
        "step_back",
    }

    if selected_strategy not in valid_strategies:
        logger.warning(
            "Unknown query-transform strategy %r; using none",
            strategy,
        )
        selected_strategy = "none"

    if selected_strategy == "auto":
        word_count = len(cleaned_query.split())
        has_question_mark = (
            "?" in cleaned_query
            or "؟" in cleaned_query
        )

        if (
            word_count <= 5
            and config.query_transform.hyde_enabled
        ):
            selected_strategy = "hyde"

        elif (
            has_question_mark
            and word_count > 15
            and config.query_transform.step_back_enabled
        ):
            selected_strategy = "step_back"

        elif config.query_transform.rag_fusion_enabled:
            selected_strategy = "fusion"

        else:
            selected_strategy = "none"

    result: Dict[str, Any] = {
        "original_query": cleaned_query,
        "strategy": selected_strategy,
        "queries": [cleaned_query],
    }

    try:
        if selected_strategy == "none":
            return result

        if selected_strategy == "hyde":
            transformed = await hyde_transform(
                cleaned_query
            )

            # Keep normal retrieval based on the original query only.
            # The hypothetical document is exposed separately so the caller
            # can use it specifically for vector retrieval.
            result["queries"] = [cleaned_query]

            if transformed != cleaned_query:
                result["hyde_document"] = transformed

            return result

        if selected_strategy == "fusion":
            result["queries"] = await rag_fusion_transform(
                cleaned_query
            )
            return result

        if selected_strategy == "step_back":
            broader_query = await step_back_transform(
                cleaned_query
            )

            result["queries"] = _deduplicate_queries(
                [cleaned_query, broader_query]
            )

            if broader_query != cleaned_query:
                result["step_back_query"] = broader_query

            return result

    except Exception as exc:
        logger.exception(
            "Query transformation failed"
        )

        result["queries"] = [cleaned_query]
        result["error"] = str(exc)

    return result