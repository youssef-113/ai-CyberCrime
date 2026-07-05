"""Cross-Encoder Reranker

Reranks retrieved results using a cross-encoder model.
Cross-encoder reranking alone solves nearly 80% of lookup-style queries.
"""
import logging
from math import exp
from typing import List, Optional

from .config import config
from .retriever import RetrievalResult

logger = logging.getLogger("rag.reranker")

_reranker_model = None


def _sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def _get_reranker():
    """Lazy cross-encoder model initialization."""
    global _reranker_model
    if _reranker_model is None and config.reranker.enabled:
        try:
            from sentence_transformers import CrossEncoder
            _reranker_model = CrossEncoder(config.reranker.model_name)
            logger.info(f"Cross-encoder reranker loaded: {config.reranker.model_name}")
        except Exception as e:
            logger.warning(f"Failed to load reranker model: {e}")
            _reranker_model = None
    return _reranker_model


def rerank(
    query: str,
    results: List[RetrievalResult],
    top_n: int = None,
) -> List[RetrievalResult]:
    """Rerank retrieval results using cross-encoder.

    Takes the top-K retrieved results and re-scores them
    with a cross-encoder for better precision.
    """
    if not config.reranker.enabled:
        logger.debug("Reranker disabled, returning original results")
        return results

    top_n = top_n or config.reranker.top_n
    model = _get_reranker()

    if model is None:
        logger.warning("Reranker model unavailable, returning original results")
        return results[:top_n]

    if not results:
        return results

    try:
        # Build query-document pairs for cross-encoder
        pairs = [(query, r.text) for r in results]

        # Cross-encoder scoring
        scores = model.predict(pairs, show_progress_bar=False)

        # Assign reranker scores (normalized to [0,1] via sigmoid) and re-sort
        for i, result in enumerate(results):
            result.combined_score = _sigmoid(float(scores[i]))

        results.sort(key=lambda r: r.combined_score, reverse=True)

        logger.debug(f"Reranked {len(results)} results, returning top {top_n}")
        return results[:top_n]

    except Exception as e:
        logger.error(f"Reranking failed: {e}")
        return results[:top_n]
