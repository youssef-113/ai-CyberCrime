"""Async Ingestion Pipeline - Celery Worker with Content-Addressable Embedding Cache

Separate ingestion pipeline that runs asynchronously behind a message queue.
Tasks: document parsing, embedding generation, indexing all happen in background workers.

Content-addressable optimization: store embeddings using hash(model_id + text)
to prevent unnecessary re-embedding during re-indexing if content hasn't changed.
"""
import json
import hashlib
import logging
import time
from typing import List, Dict, Any, Optional

from config import config

logger = logging.getLogger("rag.ingestion")

# Embedding cache: hash(model_id + text) -> embedding vector
_embedding_cache = {}

# Lazy singletons
_celery_app = None
_qdrant_client = None
_embedding_model = None


def _content_hash(model_id: str, text: str) -> str:
    """Content-addressable hash: hash(model_id + text).

    Prevents unnecessary re-embedding during re-indexing
    if the content hasn't changed.
    """
    content = f"{model_id}:{text}"
    return hashlib.sha256(content.encode()).hexdigest()


def _get_embedding_model():
    """Lazy embedding model."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(config.embedding.model_name)
    return _embedding_model


def _get_qdrant():
    """Lazy Qdrant client."""
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient
        _qdrant_client = QdrantClient(
            host=config.qdrant.host,
            port=config.qdrant.port,
            timeout=30,
        )
    return _qdrant_client


def _get_redis():
    """Get Redis client for embedding cache."""
    try:
        import redis
        client = redis.from_url(
            config.cache.redis_url.replace("/0", "/3"),  # Use DB 3 for embedding cache
            decode_responses=False,
            socket_connect_timeout=2,
        )
        return client
    except Exception as e:
        logger.warning(f"Redis unavailable for embedding cache: {e}")
        return None


def get_or_compute_embedding(text: str, model_id: str = None) -> List[float]:
    """Get embedding from cache or compute and cache it.

    Content-addressable: uses hash(model_id + text) as cache key.
    If the same text with the same model was already embedded,
    returns the cached embedding instead of recomputing.
    """
    model_id = model_id or config.embedding.model_name
    cache_key = _content_hash(model_id, text)

    # Check in-memory cache first
    if cache_key in _embedding_cache:
        return _embedding_cache[cache_key]

    # Check Redis cache
    redis = _get_redis()
    if redis is not None:
        try:
            import numpy as np
            cached = redis.get(f"emb:{cache_key}")
            if cached:
                vec = np.frombuffer(cached, dtype=np.float32).tolist()
                _embedding_cache[cache_key] = vec
                return vec
        except Exception as e:
            logger.debug(f"Redis embedding cache miss: {e}")

    # Compute embedding
    model = _get_embedding_model()
    vec = model.encode([text], normalize_embeddings=True).astype(np.float32)[0].tolist()

    # Cache it
    _embedding_cache[cache_key] = vec

    # Store in Redis
    if redis is not None:
        try:
            import numpy as np
            redis.set(f"emb:{cache_key}", np.array(vec, dtype=np.float32).tobytes())
        except Exception as e:
            logger.debug(f"Redis embedding cache store failed: {e}")

    return vec


def batch_embed(texts: List[str], model_id: str = None) -> List[List[float]]:
    """Batch embed texts with content-addressable caching.

    Only computes embeddings for texts not in cache.
    """
    model_id = model_id or config.embedding.model_name
    results = [None] * len(texts)
    uncached_indices = []
    uncached_texts = []

    # Check cache for each text
    for i, text in enumerate(texts):
        cache_key = _content_hash(model_id, text)
        if cache_key in _embedding_cache:
            results[i] = _embedding_cache[cache_key]
        else:
            uncached_indices.append(i)
            uncached_texts.append(text)

    # Batch compute uncached embeddings
    if uncached_texts:
        model = _get_embedding_model()
        vecs = model.encode(uncached_texts, normalize_embeddings=True, batch_size=32)

        for j, (idx, text) in enumerate(zip(uncached_indices, uncached_texts)):
            vec = vecs[j].tolist()
            results[idx] = vec

            # Cache
            cache_key = _content_hash(model_id, text)
            _embedding_cache[cache_key] = vec

    return results


def index_chunks(
    chunks: List[Dict],
    collection_name: str = None,
    tenant_id: str = "default",
) -> Dict[str, Any]:
    """Index chunks into Qdrant with embeddings and metadata.

    Each chunk should have: id, text, metadata
    Metadata includes: summary, keywords, source, parent_id, etc.
    """
    from qdrant_client.models import PointStruct, VectorParams, Distance

    collection_name = collection_name or config.qdrant.collection_name
    client = _get_qdrant()

    # Ensure tenant-specific collection
    if config.multi_tenant.enabled and tenant_id != "default":
        collection_name = f"{config.multi_tenant.namespace_prefix}{tenant_id}"

    # Ensure collection exists
    try:
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
    except Exception as e:
        logger.error(f"Failed to create collection: {e}")
        return {"indexed": 0, "error": str(e)}

    # Batch embed
    texts = [c["text"] for c in chunks]
    embeddings = batch_embed(texts)

    # Build Qdrant points
    points = []
    for chunk, embedding in zip(chunks, embeddings):
        # Add text to payload for retrieval
        payload = {
            **chunk.get("metadata", {}),
            "text": chunk["text"],
            "chunk_id": chunk["id"],
            "tenant_id": tenant_id,
        }

        points.append(PointStruct(
            id=hashlib.md5(chunk["id"].encode()).hexdigest()[:16],
            vector=embedding,
            payload=payload,
        ))

    # Index in batches
    batch_size = config.ingestion.batch_size
    total_indexed = 0

    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        try:
            client.upsert(
                collection_name=collection_name,
                points=batch,
            )
            total_indexed += len(batch)
            logger.info(f"Indexed batch {i // batch_size + 1}: {len(batch)} chunks")
        except Exception as e:
            logger.error(f"Failed to index batch: {e}")
            return {"indexed": total_indexed, "error": str(e)}

    return {
        "indexed": total_indexed,
        "collection": collection_name,
        "tenant_id": tenant_id,
    }


def index_articles(
    articles: List[Dict],
    tenant_id: str = "default",
) -> Dict[str, Any]:
    """Full ingestion pipeline for law articles.

    Steps:
    1. Chunk each article (parent-child strategy)
    2. Generate embeddings (with content-addressable cache)
    3. Index into Qdrant with rich metadata
    """
    from chunker import chunk_article

    all_chunks = []
    for article in articles:
        chunks = chunk_article(article)
        for chunk in chunks:
            all_chunks.append({
                "id": chunk.id,
                "text": chunk.text,
                "metadata": {
                    **chunk.metadata,
                    "parent_id": chunk.parent_id or "",
                    "token_count": chunk.token_count,
                },
            })

    logger.info(f"Created {len(all_chunks)} chunks from {len(articles)} articles")

    result = index_chunks(all_chunks, tenant_id=tenant_id)
    result["articles_processed"] = len(articles)
    result["chunks_created"] = len(all_chunks)

    return result


# ══════════════════════════════════════════════════════════════════════════
# Celery Task Definitions (for async ingestion via message queue)
# ══════════════════════════════════════════════════════════════════════════

def get_celery_app():
    """Get or create Celery application."""
    global _celery_app
    if _celery_app is None:
        try:
            from celery import Celery
            _celery_app = Celery(
                "rag_ingestion",
                broker=config.ingestion.celery_broker_url,
                backend=config.ingestion.celery_result_backend,
            )
            _celery_app.conf.update(
                task_serializer="json",
                result_serializer="json",
                accept_content=["json"],
                timezone="UTC",
                task_routes={
                    "ingestion.index_articles": {"queue": "ingestion"},
                    "ingestion.index_document": {"queue": "ingestion"},
                },
            )
            logger.info("Celery app configured")
        except ImportError:
            logger.warning("Celery not available, ingestion will be synchronous")
    return _celery_app


# Define Celery tasks if available
try:
    from celery import shared_task

    @shared_task(name="ingestion.index_articles")
    def celery_index_articles(articles: List[Dict], tenant_id: str = "default") -> Dict:
        """Celery task: async article indexing."""
        return index_articles(articles, tenant_id)

    @shared_task(name="ingestion.index_document")
    def celery_index_document(document: Dict, tenant_id: str = "default") -> Dict:
        """Celery task: async single document indexing."""
        return index_articles([document], tenant_id)

except ImportError:
    pass
