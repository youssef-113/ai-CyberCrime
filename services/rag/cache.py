"""Semantic Cache - Highest ROI Optimization

Search order:
1. Exact match in Redis
2. Semantic similarity using FAISS
3. BM25/vector retrieval handled by retriever
4. Full retrieval + generation as fallback
"""

import json
import hashlib
import time
import logging
import os
from typing import Optional, Dict, Any

import numpy as np

from config import config

logger = logging.getLogger("rag.cache")

_redis_client = None
_faiss_index = None
_cache_metadata = {}
_embedding_fn = None


def _vector_size() -> int:
    return int(os.getenv("VECTOR_SIZE", "384"))


def _get_redis():
    global _redis_client

    if _redis_client is None:
        try:
            import redis

            _redis_client = redis.from_url(
                config.cache.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            _redis_client.ping()
            logger.info("Redis cache connected")
        except Exception as e:
            logger.warning(f"Redis unavailable, cache disabled: {e}")
            _redis_client = None

    return _redis_client


def _get_embedding_fn():
    global _embedding_fn

    if _embedding_fn is None:
        from sentence_transformers import SentenceTransformer

        _embedding_fn = SentenceTransformer(config.embedding.model_name)

    return _embedding_fn


def _get_faiss_index():
    global _faiss_index

    if _faiss_index is None:
        try:
            import faiss

            dim = _vector_size()
            _faiss_index = faiss.IndexFlatIP(dim)
            logger.info(f"FAISS cache index initialized (dim={dim})")
        except ImportError:
            logger.warning("faiss not available, semantic cache disabled")
            _faiss_index = None
        except Exception as e:
            logger.warning(f"FAISS cache init failed: {e}")
            _faiss_index = None

    return _faiss_index


def _query_hash(query: str, tenant_id: str = "default") -> str:
    normalized = query.strip().lower()
    return f"rag:cache:{tenant_id}:{hashlib.md5(normalized.encode()).hexdigest()}"


class CacheHit:
    def __init__(self, response: Dict, source: str, latency_saved_ms: float = 0):
        self.response = response
        self.source = source
        self.latency_saved_ms = latency_saved_ms

    def to_dict(self):
        return {
            **self.response,
            "_cache_hit": True,
            "_cache_source": self.source,
        }


def lookup_exact(query: str, tenant_id: str = "default") -> Optional[CacheHit]:
    redis = _get_redis()

    if redis is None:
        return None

    try:
        key = _query_hash(query, tenant_id)
        cached = redis.get(key)

        if cached:
            data = json.loads(cached)
            age = time.time() - data.get("timestamp", 0)

            if age < config.cache.semantic_cache_ttl:
                logger.debug(f"Exact cache hit for query: {query[:50]}")
                return CacheHit(data["response"], "exact", latency_saved_ms=age * 1000)

            redis.delete(key)

    except Exception as e:
        logger.warning(f"Redis exact lookup error: {e}")

    return None


def lookup_semantic(query: str, tenant_id: str = "default") -> Optional[CacheHit]:
    if not config.cache.semantic_cache_enabled:
        return None

    faiss_index = _get_faiss_index()

    if faiss_index is None or faiss_index.ntotal == 0:
        return None

    try:
        embed_fn = _get_embedding_fn()
        query_vec = embed_fn.encode([query], normalize_embeddings=True).astype(np.float32)

        scores, indices = faiss_index.search(query_vec, 1)
        best_score = float(scores[0][0])
        best_idx = int(indices[0][0])

        if best_score >= config.cache.semantic_cache_threshold and best_idx in _cache_metadata:
            meta = _cache_metadata[best_idx]
            age = time.time() - meta.get("timestamp", 0)

            if age < config.cache.semantic_cache_ttl:
                logger.debug(f"Semantic cache hit (score={best_score:.3f}): {query[:50]}")
                return CacheHit(meta["response"], "semantic", latency_saved_ms=age * 1000)

    except Exception as e:
        logger.warning(f"Semantic cache lookup error: {e}")

    return None


def lookup(query: str, tenant_id: str = "default") -> Optional[CacheHit]:
    hit = lookup_exact(query, tenant_id)

    if hit:
        return hit

    hit = lookup_semantic(query, tenant_id)

    if hit:
        return hit

    return None


def store(query: str, response: Dict, tenant_id: str = "default"):
    cache_data = {
        "query": query,
        "response": response,
        "timestamp": time.time(),
        "tenant_id": tenant_id,
    }

    redis = _get_redis()

    if redis is not None:
        try:
            key = _query_hash(query, tenant_id)
            redis.setex(key, config.cache.semantic_cache_ttl, json.dumps(cache_data))
        except Exception as e:
            logger.warning(f"Redis store error: {e}")

    faiss_index = _get_faiss_index()

    if faiss_index is not None and config.cache.semantic_cache_enabled:
        try:
            embed_fn = _get_embedding_fn()
            query_vec = embed_fn.encode([query], normalize_embeddings=True).astype(np.float32)

            idx = faiss_index.ntotal
            faiss_index.add(query_vec)
            _cache_metadata[idx] = cache_data

            if faiss_index.ntotal > config.cache.faiss_cache_index_size:
                _rebuild_faiss_index()

        except Exception as e:
            logger.warning(f"FAISS store error: {e}")


def _rebuild_faiss_index():
    try:
        import faiss
    except ImportError:
        logger.warning("faiss not available, cannot rebuild semantic cache")
        return

    now = time.time()
    ttl = config.cache.semantic_cache_ttl

    valid_entries = []

    for _, meta in _cache_metadata.items():
        age = now - meta.get("timestamp", 0)

        if age < ttl:
            valid_entries.append(meta)

    _cache_metadata.clear()

    dim = _vector_size()
    new_index = faiss.IndexFlatIP(dim)

    if valid_entries:
        embed_fn = _get_embedding_fn()
        queries = [entry["query"] for entry in valid_entries]
        vecs = embed_fn.encode(queries, normalize_embeddings=True).astype(np.float32)

        new_index.add(vecs)

        for i, entry in enumerate(valid_entries):
            _cache_metadata[i] = entry

    global _faiss_index
    _faiss_index = new_index

    logger.info(f"FAISS cache rebuilt: {new_index.ntotal} valid entries")


def get_cache_stats() -> Dict[str, Any]:
    redis = _get_redis()
    faiss_index = _get_faiss_index()

    stats = {
        "redis_connected": redis is not None,
        "faiss_available": faiss_index is not None,
        "faiss_entries": faiss_index.ntotal if faiss_index else 0,
        "semantic_cache_enabled": config.cache.semantic_cache_enabled,
    }

    if redis:
        try:
            keys = redis.keys("rag:cache:*")
            stats["redis_entries"] = len(keys)
        except Exception:
            stats["redis_entries"] = "unknown"

    return stats