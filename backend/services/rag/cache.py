"""Semantic Cache - Highest ROI Optimization

Search order:
1. Exact match in Redis
2. Semantic similarity using FAISS
3. BM25/vector retrieval handled by retriever
4. Full retrieval + generation as fallback
"""

import json
import hashlib
import threading
import time
import logging
import os
from typing import Optional, Dict, Any

import numpy as np

from .config import config

logger = logging.getLogger("rag.cache")

_redis_client = None
_faiss_index = None
_cache_metadata = {}
_embedding_fn = None
_vector_size_cache = None

# Guards all read/modify/write access to _faiss_index and _cache_metadata.
# Both lookup_semantic (read) and store/_rebuild_faiss_index (write) can be
# called concurrently under FastAPI/uvicorn, and ntotal-based indexing into
# _cache_metadata is not safe without this.
_faiss_lock = threading.Lock()

# How many neighbors to pull back before filtering by tenant. A single
# global FAISS index holds every tenant's cached queries, so a raw top-1
# search can return another tenant's cache entry. We over-fetch and filter.
_SEMANTIC_SEARCH_K = 10


def _vector_size() -> int:
    """Embedding dimension for the FAISS cache index.

    Prefers the actual embedding model's output dimension so a mismatched
    VECTOR_SIZE env var can't silently break semantic caching (previously,
    a dimension mismatch was swallowed by a broad except in store() and only
    ever showed up as a warning log). Falls back to VECTOR_SIZE / 384 only
    if the model's dimension can't be determined.
    """
    global _vector_size_cache

    if _vector_size_cache is not None:
        return _vector_size_cache

    try:
        embed_fn = _get_embedding_fn()
        dim = embed_fn.get_sentence_embedding_dimension()
        if dim:
            env_dim = os.getenv("VECTOR_SIZE")
            if env_dim and int(env_dim) != dim:
                logger.warning(
                    f"VECTOR_SIZE env var ({env_dim}) does not match embedding "
                    f"model dimension ({dim}); using the model's actual dimension."
                )
            _vector_size_cache = int(dim)
            return _vector_size_cache
    except Exception as e:
        logger.debug(f"Could not determine embedding dimension from model: {e}")

    _vector_size_cache = int(os.getenv("VECTOR_SIZE", "384"))
    return _vector_size_cache


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
        from .retriever import _get_embedding_model
        _embedding_fn = _get_embedding_model()

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


def _cache_version() -> str:
    return os.getenv("CACHE_VERSION", "v1")


def _query_hash(query: str, tenant_id: str = "default") -> str:
    normalized = query.strip().lower()
    version = _cache_version()
    return f"rag:cache:{tenant_id}:{version}:{hashlib.md5(normalized.encode()).hexdigest()}"


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

    if faiss_index is None:
        return None

    try:
        embed_fn = _get_embedding_fn()
        prefixed = f"{config.embedding.query_prefix}{query}"
        query_vec = embed_fn.encode([prefixed], normalize_embeddings=True).astype(np.float32)

        with _faiss_lock:
            if faiss_index.ntotal == 0:
                return None

            k = min(_SEMANTIC_SEARCH_K, faiss_index.ntotal)
            scores, indices = faiss_index.search(query_vec, k)

            now = time.time()
            ttl = config.cache.semantic_cache_ttl

            # Walk neighbors in score order; take the first that belongs to
            # this tenant, is still known, and hasn't expired. This is what
            # keeps one tenant's semantic cache from being polluted by, or
            # leaking into, another tenant's queries.
            for score, idx in zip(scores[0], indices[0]):
                idx = int(idx)
                if idx < 0:
                    continue
                if float(score) < config.cache.semantic_cache_threshold:
                    break  # scores are sorted descending; no point continuing

                meta = _cache_metadata.get(idx)
                if meta is None:
                    continue
                if meta.get("tenant_id") != tenant_id:
                    continue

                age = now - meta.get("timestamp", 0)
                if age < ttl:
                    logger.debug(f"Semantic cache hit (score={float(score):.3f}): {query[:50]}")
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
            prefixed = f"{config.embedding.query_prefix}{query}"
            query_vec = embed_fn.encode([prefixed], normalize_embeddings=True).astype(np.float32)

            with _faiss_lock:
                idx = faiss_index.ntotal
                faiss_index.add(query_vec)
                _cache_metadata[idx] = cache_data

                needs_rebuild = faiss_index.ntotal > config.cache.faiss_cache_index_size

            if needs_rebuild:
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

    with _faiss_lock:
        valid_entries = [
            meta for meta in _cache_metadata.values()
            if now - meta.get("timestamp", 0) < ttl
        ]

        dim = _vector_size()
        new_index = faiss.IndexFlatIP(dim)
        new_metadata = {}

        if valid_entries:
            embed_fn = _get_embedding_fn()
            queries = [f"{config.embedding.query_prefix}{entry['query']}" for entry in valid_entries]
            vecs = embed_fn.encode(queries, normalize_embeddings=True).astype(np.float32)

            new_index.add(vecs)

            for i, entry in enumerate(valid_entries):
                new_metadata[i] = entry

        global _faiss_index
        _faiss_index = new_index
        _cache_metadata.clear()
        _cache_metadata.update(new_metadata)

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
            # SCAN instead of KEYS: KEYS blocks Redis for the full scan
            # duration, which is a real risk once the keyspace is large and
            # this endpoint is polled by a dashboard/monitoring job.
            count = 0
            for _ in redis.scan_iter(match="rag:cache:*", count=500):
                count += 1
            stats["redis_entries"] = count
        except Exception:
            stats["redis_entries"] = "unknown"

    return stats