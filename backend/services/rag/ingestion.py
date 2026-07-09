"""Async Ingestion Pipeline - Celery Worker with Content-Addressable Embedding Cache
 
This version indexes chunks into ChromaDB instead of Qdrant.
"""
 
import hashlib
import logging
from collections import OrderedDict
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urlunparse
 
from .config import config
from .retriever import _get_embedding_model
 
logger = logging.getLogger("rag.ingestion")
 
# Bounded in-memory cache (process-local, L1 in front of Redis).
# Prevents unbounded growth in long-running Celery workers.
_EMBEDDING_CACHE_MAX_ITEMS = 50_000
_embedding_cache: "OrderedDict[str, List[float]]" = OrderedDict()
 
_celery_app = None
_chroma_client = None
_redis_client = None
_redis_unavailable = False  # sticky flag so we don't retry-connect on every call
 
 
def _content_hash(model_id: str, text: str) -> str:
    content = f"{model_id}:{text}"
    return hashlib.sha256(content.encode()).hexdigest()
 
 
def _cache_get(key: str) -> Optional[List[float]]:
    vec = _embedding_cache.get(key)
    if vec is not None:
        _embedding_cache.move_to_end(key)
    return vec
 
 
def _cache_put(key: str, vec: List[float]) -> None:
    _embedding_cache[key] = vec
    _embedding_cache.move_to_end(key)
    if len(_embedding_cache) > _EMBEDDING_CACHE_MAX_ITEMS:
        _embedding_cache.popitem(last=False)  # evict oldest
 
 
def _get_chroma():
    """Lazy ChromaDB client (persistent by default, cloud if configured)."""
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        import os
 
        if config.chroma.client_type == "cloud":
            if not config.chroma.api_key or not config.chroma.cloud_tenant or not config.chroma.cloud_database:
                raise ValueError(
                    "ChromaDB cloud mode requires CHROMA_API_KEY, CHROMA_CLOUD_TENANT, and CHROMA_CLOUD_DATABASE"
                )
            _chroma_client = chromadb.CloudClient(
                api_key=config.chroma.api_key,
                tenant=config.chroma.cloud_tenant,
                database=config.chroma.cloud_database,
            )
        else:
            persist_dir = config.chroma.persist_directory
            if not os.path.isabs(persist_dir):
                base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                persist_dir = os.path.join(base, persist_dir)
            os.makedirs(persist_dir, exist_ok=True)
            _chroma_client = chromadb.PersistentClient(path=persist_dir)
 
    return _chroma_client
 
 
def _embedding_cache_redis_url() -> str:
    """Return the configured redis_url pointed at the embedding-cache DB (index 3),
    regardless of what DB index (or none) was originally configured.
 
    Avoids the previous ``url.replace("/0", "/3")`` hack, which silently broke
    (or pointed at the wrong DB) for any URL not ending in exactly "/0".
    """
    parsed = urlparse(config.cache.redis_url)
    new_path = "/3"
    return urlunparse(parsed._replace(path=new_path))
 
 
def _get_redis():
    """Lazy, cached Redis client for the embedding cache.
 
    Previously this opened a brand-new connection (with a 2s connect timeout)
    on every single embedding lookup. Now it's created once and reused, and a
    failed connection is remembered so we don't keep retrying on every call.
    """
    global _redis_client, _redis_unavailable
 
    if _redis_unavailable:
        return None
 
    if _redis_client is None:
        try:
            import redis
 
            _redis_client = redis.from_url(
                _embedding_cache_redis_url(),
                decode_responses=False,
                socket_connect_timeout=2,
            )
            _redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis unavailable for embedding cache: {e}")
            _redis_client = None
            _redis_unavailable = True
            return None
 
    return _redis_client
 
 
def _redis_mget_embeddings(redis, cache_keys: List[str]) -> Dict[str, List[float]]:
    """Fetch multiple embeddings from Redis in one round trip."""
    import numpy as np
 
    if not cache_keys:
        return {}
 
    redis_keys = [f"emb:{k}" for k in cache_keys]
    try:
        values = redis.mget(redis_keys)
    except Exception as e:
        logger.debug(f"Redis embedding cache mget failed: {e}")
        return {}
 
    found = {}
    for key, raw in zip(cache_keys, values):
        if raw is not None:
            found[key] = np.frombuffer(raw, dtype=np.float32).tolist()
    return found
 
 
def _redis_mset_embeddings(redis, items: Dict[str, List[float]]) -> None:
    """Store multiple embeddings in Redis in one round trip."""
    import numpy as np
 
    if not items:
        return
    try:
        pipe = redis.pipeline(transaction=False)
        for key, vec in items.items():
            pipe.set(f"emb:{key}", np.array(vec, dtype=np.float32).tobytes())
        pipe.execute()
    except Exception as e:
        logger.debug(f"Redis embedding cache store failed: {e}")
 
 
def get_or_compute_embedding(text: str, model_id: str = None) -> List[float]:
    model_id = model_id or config.embedding.model_name
    text = f"{config.embedding.passage_prefix}{text}"
    cache_key = _content_hash(model_id, text)
 
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
 
    redis = _get_redis()
    if redis is not None:
        found = _redis_mget_embeddings(redis, [cache_key])
        if cache_key in found:
            vec = found[cache_key]
            _cache_put(cache_key, vec)
            return vec
 
    model = _get_embedding_model()
    vec = model.encode([text], normalize_embeddings=True).astype("float32")[0].tolist()
 
    _cache_put(cache_key, vec)
 
    if redis is not None:
        _redis_mset_embeddings(redis, {cache_key: vec})
 
    return vec
 
 
def batch_embed(texts: List[str], model_id: str = None) -> List[List[float]]:
    """Embed a batch of texts, checking the in-memory cache, then Redis,
    before falling back to the embedding model.
 
    Previously this only checked the in-process ``_embedding_cache`` dict,
    which meant Redis (the persistent cache) was never consulted or
    populated during ingestion -- every worker restart forced full
    recomputation of embeddings for the whole corpus.
    """
    model_id = model_id or config.embedding.model_name
    texts = [f"{config.embedding.passage_prefix}{t}" for t in texts]
    results: List[Optional[List[float]]] = [None] * len(texts)
 
    cache_keys = [_content_hash(model_id, t) for t in texts]
 
    # 1. Check in-memory (L1) cache.
    still_missing_idx = []
    for i, key in enumerate(cache_keys):
        vec = _cache_get(key)
        if vec is not None:
            results[i] = vec
        else:
            still_missing_idx.append(i)
 
    # 2. Check Redis (L2) cache for anything still missing.
    redis = _get_redis()
    if redis is not None and still_missing_idx:
        keys_to_check = [cache_keys[i] for i in still_missing_idx]
        found = _redis_mget_embeddings(redis, keys_to_check)
 
        remaining_idx = []
        for i in still_missing_idx:
            key = cache_keys[i]
            if key in found:
                vec = found[key]
                results[i] = vec
                _cache_put(key, vec)
            else:
                remaining_idx.append(i)
        still_missing_idx = remaining_idx
 
    # 3. Compute anything still missing via the embedding model.
    if still_missing_idx:
        uncached_texts = [texts[i] for i in still_missing_idx]
        model = _get_embedding_model()
        vecs = model.encode(
            uncached_texts,
            normalize_embeddings=True,
            batch_size=32,
        )
 
        newly_computed = {}
        for idx, vec_arr in zip(still_missing_idx, vecs):
            vec = vec_arr.tolist()
            key = cache_keys[idx]
            results[idx] = vec
            _cache_put(key, vec)
            newly_computed[key] = vec
 
        if redis is not None:
            _redis_mset_embeddings(redis, newly_computed)
 
    return results  # type: ignore[return-value]
 
 
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
    from .chunker import chunk_article
 
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