"""Async Ingestion Pipeline - Celery Worker with Content-Addressable Embedding Cache

This version indexes chunks into ChromaDB instead of Qdrant.
"""

import hashlib
import logging
from typing import List, Dict, Any

from config import config

logger = logging.getLogger("rag.ingestion")

_embedding_cache = {}

_celery_app = None
_chroma_client = None
_embedding_model = None


def _content_hash(model_id: str, text: str) -> str:
    content = f"{model_id}:{text}"
    return hashlib.sha256(content.encode()).hexdigest()


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(config.embedding.model_name)
    return _embedding_model


def _get_chroma():
    """Lazy ChromaDB HTTP client."""
    global _chroma_client
    if _chroma_client is None:
        import chromadb

        host = getattr(config, "chroma", None)
        chroma_host = getattr(host, "host", "chromadb") if host else "chromadb"
        chroma_port = getattr(host, "port", 8000) if host else 8000

        _chroma_client = chromadb.HttpClient(
            host=chroma_host,
            port=chroma_port,
        )

    return _chroma_client


def _get_redis():
    try:
        import redis

        client = redis.from_url(
            config.cache.redis_url.replace("/0", "/3"),
            decode_responses=False,
            socket_connect_timeout=2,
        )
        return client
    except Exception as e:
        logger.warning(f"Redis unavailable for embedding cache: {e}")
        return None


def get_or_compute_embedding(text: str, model_id: str = None) -> List[float]:
    model_id = model_id or config.embedding.model_name
    cache_key = _content_hash(model_id, text)

    if cache_key in _embedding_cache:
        return _embedding_cache[cache_key]

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

    model = _get_embedding_model()
    vec = model.encode([text], normalize_embeddings=True).astype("float32")[0].tolist()

    _embedding_cache[cache_key] = vec

    if redis is not None:
        try:
            import numpy as np

            redis.set(f"emb:{cache_key}", np.array(vec, dtype=np.float32).tobytes())
        except Exception as e:
            logger.debug(f"Redis embedding cache store failed: {e}")

    return vec


def batch_embed(texts: List[str], model_id: str = None) -> List[List[float]]:
    model_id = model_id or config.embedding.model_name
    results = [None] * len(texts)
    uncached_indices = []
    uncached_texts = []

    for i, text in enumerate(texts):
        cache_key = _content_hash(model_id, text)
        if cache_key in _embedding_cache:
            results[i] = _embedding_cache[cache_key]
        else:
            uncached_indices.append(i)
            uncached_texts.append(text)

    if uncached_texts:
        model = _get_embedding_model()
        vecs = model.encode(
            uncached_texts,
            normalize_embeddings=True,
            batch_size=32,
        )

        for j, (idx, text) in enumerate(zip(uncached_indices, uncached_texts)):
            vec = vecs[j].tolist()
            results[idx] = vec

            cache_key = _content_hash(model_id, text)
            _embedding_cache[cache_key] = vec

    return results


def index_chunks(
    chunks: List[Dict],
    collection_name: str = None,
    tenant_id: str = "default",
) -> Dict[str, Any]:
    """Index chunks into ChromaDB with embeddings and metadata."""

    if not chunks:
        return {
            "indexed": 0,
            "collection": collection_name or "egyptian_law",
            "tenant_id": tenant_id,
        }

    collection_name = collection_name or "egyptian_law"

    if config.multi_tenant.enabled and tenant_id != "default":
        collection_name = f"{config.multi_tenant.namespace_prefix}{tenant_id}"

    try:
        client = _get_chroma()
        collection = client.get_or_create_collection(name=collection_name)
    except Exception as e:
        logger.error(f"Failed to connect/create ChromaDB collection: {e}")
        return {"indexed": 0, "error": str(e)}

    texts = [chunk["text"] for chunk in chunks]
    embeddings = batch_embed(texts)

    ids = []
    metadatas = []

    for chunk in chunks:
        chunk_id = str(chunk["id"])

        metadata = {
            **chunk.get("metadata", {}),
            "chunk_id": chunk_id,
            "tenant_id": tenant_id,
        }

        # Chroma metadata values should be simple types only.
        clean_metadata = {}
        for key, value in metadata.items():
            if value is None:
                clean_metadata[key] = ""
            elif isinstance(value, (str, int, float, bool)):
                clean_metadata[key] = value
            else:
                clean_metadata[key] = str(value)

        ids.append(chunk_id)
        metadatas.append(clean_metadata)

    batch_size = config.ingestion.batch_size
    total_indexed = 0

    for i in range(0, len(chunks), batch_size):
        batch_ids = ids[i:i + batch_size]
        batch_texts = texts[i:i + batch_size]
        batch_embeddings = embeddings[i:i + batch_size]
        batch_metadatas = metadatas[i:i + batch_size]

        try:
            # Use upsert so repeated indexing does not fail because of duplicate IDs.
            collection.upsert(
                ids=batch_ids,
                documents=batch_texts,
                embeddings=batch_embeddings,
                metadatas=batch_metadatas,
            )
            total_indexed += len(batch_ids)
            logger.info(f"Indexed ChromaDB batch {i // batch_size + 1}: {len(batch_ids)} chunks")
        except Exception as e:
            logger.error(f"Failed to index ChromaDB batch: {e}")
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
    1. Chunk each article
    2. Generate embeddings
    3. Index into ChromaDB
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


def get_celery_app():
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


try:
    from celery import shared_task

    @shared_task(name="ingestion.index_articles")
    def celery_index_articles(articles: List[Dict], tenant_id: str = "default") -> Dict:
        return index_articles(articles, tenant_id)

    @shared_task(name="ingestion.index_document")
    def celery_index_document(document: Dict, tenant_id: str = "default") -> Dict:
        return index_articles([document], tenant_id)

except ImportError:
    pass