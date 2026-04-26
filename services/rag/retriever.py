"""Hybrid Retriever - Vector Search + BM25 with Minimum Vector Threshold

Production trick: BM25 should only boost chunks that already pass
a minimum vector similarity threshold. Otherwise, keyword-heavy chunks
can pollute top-K results and hurt retrieval quality.
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import numpy as np

from config import config

logger = logging.getLogger("rag.retriever")

# Lazy singletons
_qdrant_client = None
_embedding_model = None
_bm25_corpus = None


def _get_qdrant():
    """Lazy Qdrant client."""
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient
        _qdrant_client = QdrantClient(
            host=config.qdrant.host,
            port=config.qdrant.port,
            timeout=10,
        )
    return _qdrant_client


def _get_embedding_model():
    """Lazy embedding model."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(config.embedding.model_name)
    return _embedding_model


@dataclass
class RetrievalResult:
    """A single retrieval result with scores."""
    id: str
    text: str
    metadata: Dict[str, Any]
    vector_score: float = 0.0
    bm25_score: float = 0.0
    combined_score: float = 0.0
    parent_text: Optional[str] = None  # parent chunk text for context

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "text": self.parent_text or self.text,  # Return parent context if available
            "child_text": self.text if self.parent_text else None,
            "metadata": self.metadata,
            "vector_score": round(self.vector_score, 4),
            "bm25_score": round(self.bm25_score, 4),
            "combined_score": round(self.combined_score, 4),
        }


def _ensure_collection(client, collection_name: str):
    """Ensure Qdrant collection exists."""
    from qdrant_client.models import Distance, VectorParams

    collections = client.get_collections().collections
    existing = [c.name for c in collections]

    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=config.qdrant.vector_size,
                distance=Distance.COSINE,
            ),
        )
        logger.info(f"Created Qdrant collection: {collection_name}")


def _vector_search(
    query: str,
    collection_name: str,
    top_k: int,
    tenant_id: str = "default",
) -> List[RetrievalResult]:
    """Vector similarity search using Qdrant."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    client = _get_qdrant()
    model = _get_embedding_model()

    query_vec = model.encode([query], normalize_embeddings=True).astype(np.float32)[0]

    # Build filter for tenant isolation
    query_filter = None
    if config.multi_tenant.enabled and tenant_id != "default":
        query_filter = Filter(
            must=[FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))]
        )

    results = client.search(
        collection_name=collection_name,
        query_vec=query_vec.tolist(),
        limit=top_k,
        with_payload=True,
        query_filter=query_filter,
    )

    retrieval_results = []
    for r in results:
        payload = r.payload or {}
        parent_text = None

        # If this is a child chunk, fetch parent text for context
        if payload.get("chunk_type") == "child" and payload.get("parent_id"):
            parent_text = _fetch_parent_text(client, collection_name, payload["parent_id"])

        retrieval_results.append(RetrievalResult(
            id=str(r.id),
            text=payload.get("text", ""),
            metadata=payload,
            vector_score=float(r.score),
            parent_text=parent_text,
        ))

    return retrieval_results


def _fetch_parent_text(client, collection_name: str, parent_id: str) -> Optional[str]:
    """Fetch parent chunk text for context expansion."""
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        results, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[FieldCondition(key="chunk_id", match=MatchValue(value=parent_id))]
            ),
            limit=1,
            with_payload=True,
        )

        if results:
            return results[0].payload.get("text", "")
    except Exception as e:
        logger.warning(f"Failed to fetch parent chunk {parent_id}: {e}")

    return None


def _bm25_search(
    query: str,
    collection_name: str,
    top_k: int,
    tenant_id: str = "default",
) -> Dict[str, float]:
    """BM25 keyword search using Qdrant full-text search."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    client = _get_qdrant()

    # Qdrant supports full-text search via payload index
    query_filter = None
    if config.multi_tenant.enabled and tenant_id != "default":
        query_filter = Filter(
            must=[FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))]
        )

    try:
        results = client.search(
            collection_name=collection_name,
            query_vec=_get_embedding_model().encode([query], normalize_embeddings=True).astype(np.float32)[0].tolist(),
            limit=top_k * 2,  # fetch more for BM25 filtering
            with_payload=True,
            query_filter=query_filter,
        )

        # Simple BM25-like scoring based on keyword overlap
        query_terms = set(query.lower().split())
        bm25_scores = {}

        for r in results:
            payload = r.payload or {}
            text = payload.get("text", "").lower()
            keywords = payload.get("keywords", [])

            # Count term overlaps
            text_terms = set(text.split())
            keyword_set = {k.lower() for k in keywords} if isinstance(keywords, list) else set()

            overlap = len(query_terms & text_terms) + len(query_terms & keyword_set) * 2
            if overlap > 0:
                bm25_scores[str(r.id)] = overlap / max(len(query_terms), 1)

        return bm25_scores
    except Exception as e:
        logger.warning(f"BM25 search error: {e}")
        return {}


def hybrid_retrieve(
    query: str,
    top_k: int = None,
    tenant_id: str = "default",
    collection_name: str = None,
) -> List[RetrievalResult]:
    """Hybrid retrieval: Vector + BM25 with minimum vector threshold.

    BM25 only boosts chunks that already pass min_vector_similarity.
    This prevents keyword-heavy chunks from polluting results.
    """
    top_k = top_k or config.retriever.top_k
    collection_name = collection_name or config.qdrant.collection_name

    # Ensure tenant-specific collection if multi-tenant
    if config.multi_tenant.enabled and tenant_id != "default":
        collection_name = f"{config.multi_tenant.namespace_prefix}{tenant_id}"

    # Vector search (primary)
    vector_results = _vector_search(query, collection_name, top_k, tenant_id)

    # BM25 search (secondary boost)
    bm25_scores = _bm25_search(query, collection_name, top_k, tenant_id)

    # Combine scores with minimum vector threshold for BM25 boost
    min_vec_sim = config.retriever.min_vector_similarity
    vec_weight = config.retriever.vector_weight
    bm25_weight = config.retriever.bm25_weight

    for result in vector_results:
        bm25 = bm25_scores.get(result.id, 0.0)

        # Production trick: BM25 only boosts if vector score passes threshold
        if result.vector_score >= min_vec_sim:
            result.bm25_score = bm25
            result.combined_score = (
                vec_weight * result.vector_score +
                bm25_weight * bm25
            )
        else:
            # Below threshold: BM25 cannot rescue this chunk
            result.combined_score = vec_weight * result.vector_score

    # Sort by combined score
    vector_results.sort(key=lambda r: r.combined_score, reverse=True)

    return vector_results[:top_k]


def get_retriever_stats() -> Dict[str, Any]:
    """Return retriever statistics."""
    client = _get_qdrant()
    stats = {}

    try:
        collection_name = config.qdrant.collection_name
        info = client.get_collection(collection_name)
        stats["vector_count"] = info.points_count
        stats["vector_size"] = info.config.params.vectors.size
        stats["status"] = info.status.value
    except Exception as e:
        stats["error"] = str(e)

    return stats
