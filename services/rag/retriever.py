"""Hybrid Retriever - ChromaDB Vector Search + BM25-like Keyword Boost"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import numpy as np

from .config import config

logger = logging.getLogger("rag.retriever")

_chroma_client = None
_embedding_model = None


def _get_chroma():
    global _chroma_client

    if _chroma_client is None:
        import chromadb
        _chroma_client = chromadb.HttpClient(
            host=config.chroma.host,
            port=config.chroma.port,
        )

    return _chroma_client


def _get_embedding_model():
    global _embedding_model

    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(config.embedding.model_name)

    return _embedding_model


@dataclass
class RetrievalResult:
    id: str
    text: str
    metadata: Dict[str, Any]
    vector_score: float = 0.0
    bm25_score: float = 0.0
    combined_score: float = 0.0
    parent_text: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "text": self.parent_text or self.text,
            "child_text": self.text if self.parent_text else None,
            "metadata": self.metadata,
            "vector_score": round(self.vector_score, 4),
            "bm25_score": round(self.bm25_score, 4),
            "combined_score": round(self.combined_score, 4),
        }


def _get_collection(collection_name: str):
    client = _get_chroma()
    return client.get_or_create_collection(name=collection_name)


def _fetch_parent_text(collection, parent_id: str) -> Optional[str]:
    if not parent_id:
        return None

    try:
        result = collection.get(ids=[parent_id], include=["documents", "metadatas"])
        documents = result.get("documents") or []
        if documents:
            return documents[0]
    except Exception as e:
        logger.warning(f"Failed to fetch parent chunk {parent_id}: {e}")

    return None


def _vector_search(
    query: str,
    collection_name: str,
    top_k: int,
    tenant_id: str = "default",
) -> List[RetrievalResult]:

    collection = _get_collection(collection_name)
    model = _get_embedding_model()

    query_vec = model.encode([query], normalize_embeddings=True).astype(np.float32)[0].tolist()

    query_kwargs = {
        "query_embeddings": [query_vec],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }

    if config.multi_tenant.enabled and tenant_id != "default":
        query_kwargs["where"] = {"tenant_id": tenant_id}

    try:
        result = collection.query(**query_kwargs)
    except Exception as e:
        logger.error(f"ChromaDB vector search failed: {e}")
        return []

    raw_ids = result.get("ids", [])
    raw_docs = result.get("documents", [])
    raw_meta = result.get("metadatas", [])
    raw_dist = result.get("distances", [])

    ids = raw_ids[0] if raw_ids and isinstance(raw_ids[0], list) else raw_ids
    documents = raw_docs[0] if raw_docs and isinstance(raw_docs[0], list) else raw_docs
    metadatas = raw_meta[0] if raw_meta and isinstance(raw_meta[0], list) else raw_meta
    distances = raw_dist[0] if raw_dist and isinstance(raw_dist[0], list) else raw_dist

    retrieval_results = []

    for idx, chunk_id in enumerate(ids):
        text = documents[idx] if idx < len(documents) else ""
        metadata = metadatas[idx] if idx < len(metadatas) and metadatas[idx] else {}
        distance = distances[idx] if idx < len(distances) else 999.0

        vector_score = 1.0 / (1.0 + float(distance))

        parent_text = None
        if metadata.get("chunk_type") == "child" and metadata.get("parent_id"):
            parent_text = _fetch_parent_text(collection, metadata.get("parent_id"))

        retrieval_results.append(
            RetrievalResult(
                id=str(chunk_id),
                text=text,
                metadata=metadata,
                vector_score=vector_score,
                parent_text=parent_text,
            )
        )

    logger.info(f"Vector search returned {len(retrieval_results)} results")
    return retrieval_results


def _keywords_to_set(keywords: Any) -> set:
    if not keywords:
        return set()

    if isinstance(keywords, list):
        return {str(k).lower().strip() for k in keywords if str(k).strip()}

    if isinstance(keywords, str):
        return {k.lower().strip() for k in keywords.replace(",", " ").split() if k.strip()}

    return set()


def _bm25_like_scores(query: str, results: List[RetrievalResult]) -> Dict[str, float]:
    query_terms = {term.lower().strip() for term in query.split() if term.strip()}
    scores = {}

    if not query_terms:
        return scores

    for result in results:
        text = (result.text or "").lower()
        parent_text = (result.parent_text or "").lower()
        full_text = text + " " + parent_text

        text_terms = set(full_text.split())
        keyword_terms = _keywords_to_set(result.metadata.get("keywords", ""))

        overlap = len(query_terms & text_terms)
        overlap += len(query_terms & keyword_terms) * 2

        if overlap > 0:
            scores[result.id] = overlap / max(len(query_terms), 1)

    return scores


def hybrid_retrieve(
    query: str,
    top_k: int = None,
    tenant_id: str = "default",
    collection_name: str = None,
) -> List[RetrievalResult]:

    top_k = top_k or config.retriever.top_k
    collection_name = collection_name or config.chroma.collection_name

    if config.multi_tenant.enabled and tenant_id != "default":
        collection_name = f"{config.multi_tenant.namespace_prefix}{tenant_id}"

    vector_results = _vector_search(
        query=query,
        collection_name=collection_name,
        top_k=top_k,
        tenant_id=tenant_id,
    )

    if not vector_results:
        return []

    bm25_scores = _bm25_like_scores(query, vector_results)

    vec_weight = config.retriever.vector_weight
    bm25_weight = config.retriever.bm25_weight

    for result in vector_results:
        bm25 = bm25_scores.get(result.id, 0.0)
        result.bm25_score = bm25
        result.combined_score = (vec_weight * result.vector_score) + (bm25_weight * bm25)

    vector_results.sort(key=lambda r: r.combined_score, reverse=True)

    logger.info(f"Hybrid retrieve returned {len(vector_results[:top_k])} results")
    return vector_results[:top_k]


def get_retriever_stats() -> Dict[str, Any]:
    stats = {
        "vector_db": "chromadb",
        "host": config.chroma.host,
        "port": config.chroma.port,
        "collection": config.chroma.collection_name,
    }

    try:
        client = _get_chroma()
        collection = client.get_or_create_collection(name=config.chroma.collection_name)

        stats["document_count"] = collection.count()
        stats["status"] = "ok"

    except Exception as e:
        stats["status"] = "error"
        stats["error"] = str(e)

    return stats