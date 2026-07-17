"""Exact Redis cache and process-local FAISS semantic cache."""

import hashlib
import json
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

import numpy as np

from .config import config

logger = logging.getLogger("rag.cache")

_redis_client = None
_redis_next_retry_at = 0.0
_faiss_index = None
_cache_metadata: Dict[int, Dict[str, Any]] = {}
_query_to_index: Dict[str, int] = {}
_embedding_fn = None
_vector_size_cache = None
_faiss_lock = threading.RLock()

_REDIS_RETRY_COOLDOWN_SECONDS = getattr(config.cache, "redis_retry_interval_seconds", 60)
_SEMANTIC_SEARCH_K = 10


def _vector_size() -> int:
    global _vector_size_cache
    if _vector_size_cache is not None:
        return _vector_size_cache

    try:
        embed_fn = _get_embedding_fn()
        dimension = embed_fn.get_sentence_embedding_dimension()
        if dimension:
            env_dimension = os.getenv("VECTOR_SIZE")
            if env_dimension and int(env_dimension) != int(dimension):
                logger.warning(
                    "VECTOR_SIZE=%s differs from model dimension=%s; using model dimension",
                    env_dimension,
                    dimension,
                )
            _vector_size_cache = int(dimension)
            return _vector_size_cache
    except Exception:
        logger.exception("Could not determine embedding dimension from model")

    _vector_size_cache = int(os.getenv("VECTOR_SIZE", "384"))
    return _vector_size_cache


def _mark_redis_failed() -> None:
    global _redis_client, _redis_next_retry_at
    _redis_client = None
    _redis_next_retry_at = time.monotonic() + _REDIS_RETRY_COOLDOWN_SECONDS


def _get_redis():
    global _redis_client

    if _redis_client is not None:
        return _redis_client
    if time.monotonic() < _redis_next_retry_at:
        return None

    try:
        import redis

        client = redis.from_url(
            config.cache.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        _redis_client = client
        logger.info("Redis cache connected")
    except Exception as exc:
        logger.warning("Redis unavailable; retrying after cooldown: %s", exc)
        _mark_redis_failed()

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

            _faiss_index = faiss.IndexFlatIP(_vector_size())
            logger.info("FAISS semantic cache initialized")
        except ImportError:
            logger.warning("faiss not available; semantic cache disabled")
        except Exception:
            logger.exception("FAISS semantic cache initialization failed")
    return _faiss_index


def _cache_version() -> str:
    return os.getenv("CACHE_VERSION", "v1")


def _normalise_query(query: str) -> str:
    return " ".join(query.strip().casefold().split())


def _query_hash(query: str, tenant_id: str = "default") -> str:
    digest = hashlib.sha256(_normalise_query(query).encode("utf-8")).hexdigest()
    return f"rag:cache:{tenant_id}:{_cache_version()}:{digest}"


def _semantic_identity(query: str, tenant_id: str) -> str:
    return f"{tenant_id}:{_cache_version()}:{_normalise_query(query)}"


class CacheHit:
    def __init__(
        self,
        response: Dict[str, Any],
        source: str,
        cache_age_ms: float = 0,
    ) -> None:
        self.response = response
        self.source = source
        self.cache_age_ms = cache_age_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.response,
            "_cache_hit": True,
            "_cache_source": self.source,
            "_cache_age_ms": self.cache_age_ms,
        }


def lookup_exact(query: str, tenant_id: str = "default") -> Optional[CacheHit]:
    redis_client = _get_redis()
    if redis_client is None:
        return None

    try:
        key = _query_hash(query, tenant_id)
        raw = redis_client.get(key)
        if not raw:
            return None

        data = json.loads(raw)
        age = time.time() - float(data.get("timestamp", 0))
        if age < config.cache.semantic_cache_ttl:
            return CacheHit(data["response"], "exact", cache_age_ms=age * 1000)

        redis_client.delete(key)
    except Exception as exc:
        logger.warning("Redis exact lookup failed: %s", exc)
        _mark_redis_failed()

    return None


def lookup_semantic(query: str, tenant_id: str = "default") -> Optional[CacheHit]:
    if not config.cache.semantic_cache_enabled:
        return None

    faiss_index = _get_faiss_index()
    if faiss_index is None:
        return None

    try:
        vector = _get_embedding_fn().encode(
            [f"{config.embedding.query_prefix}{query}"],
            normalize_embeddings=True,
        ).astype(np.float32)

        with _faiss_lock:
            if faiss_index.ntotal == 0:
                return None

            search_k = min(max(_SEMANTIC_SEARCH_K, faiss_index.ntotal), faiss_index.ntotal)
            scores, indices = faiss_index.search(vector, search_k)
            now = time.time()

            for score, index in zip(scores[0], indices[0]):
                index = int(index)
                if index < 0 or float(score) < config.cache.semantic_cache_threshold:
                    continue

                metadata = _cache_metadata.get(index)
                if not metadata or metadata.get("tenant_id") != tenant_id:
                    continue

                age = now - float(metadata.get("timestamp", 0))
                if age < config.cache.semantic_cache_ttl:
                    return CacheHit(
                        metadata["response"],
                        "semantic",
                        cache_age_ms=age * 1000,
                    )
    except Exception:
        logger.exception("Semantic cache lookup failed")

    return None


def lookup(query: str, tenant_id: str = "default") -> Optional[CacheHit]:
    return lookup_exact(query, tenant_id) or lookup_semantic(query, tenant_id)


def store(query: str, response: Dict[str, Any], tenant_id: str = "default") -> None:
    cache_data = {
        "query": query,
        "response": response,
        "timestamp": time.time(),
        "tenant_id": tenant_id,
    }

    redis_client = _get_redis()
    if redis_client is not None:
        try:
            redis_client.setex(
                _query_hash(query, tenant_id),
                config.cache.semantic_cache_ttl,
                json.dumps(cache_data, ensure_ascii=False, default=str),
            )
        except Exception as exc:
            logger.warning("Redis cache store failed: %s", exc)
            _mark_redis_failed()

    faiss_index = _get_faiss_index()
    if faiss_index is None or not config.cache.semantic_cache_enabled:
        return

    try:
        vector = _get_embedding_fn().encode(
            [f"{config.embedding.query_prefix}{query}"],
            normalize_embeddings=True,
        ).astype(np.float32)
        identity = _semantic_identity(query, tenant_id)

        with _faiss_lock:
            existing_index = _query_to_index.get(identity)
            if existing_index is not None:
                _cache_metadata[existing_index] = cache_data
                return

            index = faiss_index.ntotal
            faiss_index.add(vector)
            _cache_metadata[index] = cache_data
            _query_to_index[identity] = index
            needs_rebuild = faiss_index.ntotal > config.cache.faiss_cache_index_size

        if needs_rebuild:
            _rebuild_faiss_index()
    except Exception:
        logger.exception("FAISS cache store failed")


def _rebuild_faiss_index() -> None:
    global _faiss_index

    try:
        import faiss
    except ImportError:
        return

    now = time.time()
    ttl = config.cache.semantic_cache_ttl

    with _faiss_lock:
        snapshot = [
            dict(metadata)
            for metadata in _cache_metadata.values()
            if now - float(metadata.get("timestamp", 0)) < ttl
        ]

    new_index = faiss.IndexFlatIP(_vector_size())
    new_metadata: Dict[int, Dict[str, Any]] = {}
    new_query_to_index: Dict[str, int] = {}

    if snapshot:
        queries = [
            f"{config.embedding.query_prefix}{entry['query']}" for entry in snapshot
        ]
        vectors = _get_embedding_fn().encode(
            queries,
            normalize_embeddings=True,
        ).astype(np.float32)
        new_index.add(vectors)

        for index, entry in enumerate(snapshot):
            new_metadata[index] = entry
            new_query_to_index[
                _semantic_identity(entry["query"], entry["tenant_id"])
            ] = index

    with _faiss_lock:
        _faiss_index = new_index
        _cache_metadata.clear()
        _cache_metadata.update(new_metadata)
        _query_to_index.clear()
        _query_to_index.update(new_query_to_index)

    logger.info("FAISS cache rebuilt with %s entries", new_index.ntotal)


def get_cache_stats() -> Dict[str, Any]:
    redis_client = _redis_client
    faiss_index = _faiss_index

    stats: Dict[str, Any] = {
        "redis_connected": redis_client is not None,
        "faiss_available": faiss_index is not None,
        "faiss_entries": faiss_index.ntotal if faiss_index is not None else 0,
        "semantic_cache_enabled": config.cache.semantic_cache_enabled,
    }

    if redis_client is not None:
        try:
            stats["redis_entries"] = sum(
                1 for _ in redis_client.scan_iter(match="rag:cache:*", count=500)
            )
        except Exception:
            stats["redis_entries"] = "unknown"

    return stats
