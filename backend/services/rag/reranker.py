"""Cross-Encoder Reranker

Reranks retrieved results using a cross-encoder model.
"""

import logging
from math import exp
from typing import List

from .config import config
from .retriever import RetrievalResult

logger = logging.getLogger("rag.reranker")

_reranker_model = None
_reranker_load_failed = False


def _sigmoid(x: float) -> float:
    """Convert a raw binary-relevance logit to a value between 0 and 1."""
    try:
        return 1.0 / (1.0 + exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def _get_reranker():
    """Lazily initialize and return the cross-encoder model."""
    global _reranker_model, _reranker_load_failed

    if not config.reranker.enabled:
        return None

    if _reranker_model is not None:
        return _reranker_model

    if _reranker_load_failed:
        return None

    try:
        from sentence_transformers import CrossEncoder

        _reranker_model = CrossEncoder(
            config.reranker.model_name
        )

        logger.info(
            "Cross-encoder reranker loaded: %s",
            config.reranker.model_name,
        )

    except Exception:
        _reranker_load_failed = True
        _reranker_model = None

        logger.exception(
            "Failed to load cross-encoder reranker: %s",
            config.reranker.model_name,
        )

    return _reranker_model


def rerank(
    query: str,
    results: List[RetrievalResult],
    top_n: int = None,
) -> List[RetrievalResult]:
    """Rerank retrieved results using a cross-encoder.

    The retriever first returns candidate chunks. This function then
    evaluates each query-document pair using a cross-encoder and returns
    the highest-scoring results.

    When a child chunk contains parent context, both texts are supplied
    to the reranker so that it sees the relevant passage and its context.
    """

    if not results:
        return []

    if top_n is None:
        top_n = config.reranker.top_n

    top_n = max(0, min(top_n, len(results)))

    if top_n == 0:
        return []

    if not config.reranker.enabled:
        logger.debug(
            "Reranker disabled, returning original results"
        )
        return results[:top_n]

    model = _get_reranker()

    if model is None:
        logger.warning(
            "Reranker model unavailable, returning original results"
        )
        return results[:top_n]

    try:
        original_scores = [
            result.combined_score
            for result in results
        ]

        pairs = [
            (
                query,
                (
                    f"{result.text}\n\n"
                    f"Parent context:\n{result.parent_text}"
                    if result.parent_text
                    else result.text
                ),
            )
            for result in results
        ]

        batch_size = getattr(
            config.reranker,
            "batch_size",
            16,
        )

        scores = model.predict(
            pairs,
            batch_size=batch_size,
            show_progress_bar=False,
        )

        raw_scores = [
            float(score)
            for score in scores
        ]

        if len(raw_scores) != len(results):
            raise ValueError(
                "Reranker returned an unexpected number of scores: "
                f"{len(raw_scores)} scores for "
                f"{len(results)} results"
            )

        raw_score_range = (
            max(raw_scores)
            - min(raw_scores)
        )

        if raw_score_range < 1e-6:
            logger.debug(
                "Reranker scores are not discriminative; "
                "preserving original retrieval order"
            )

            for result, original_score in zip(
                results,
                original_scores,
            ):
                result.combined_score = original_score

            return results[:top_n]

        reranker_scores = [
            _sigmoid(score)
            for score in raw_scores
        ]

        for result, reranker_score in zip(
            results,
            reranker_scores,
        ):
            result.combined_score = reranker_score

        reranked_results = sorted(
            results,
            key=lambda result: result.combined_score,
            reverse=True,
        )

        logger.debug(
            "Reranked %d results, returning top %d",
            len(results),
            top_n,
        )

        return reranked_results[:top_n]

    except Exception:
        logger.exception(
            "Cross-encoder reranking failed"
        )
        return results[:top_n]