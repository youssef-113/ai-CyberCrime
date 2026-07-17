"""RAG Service - Production Legal Retrieval Pipeline

Architecture: Separate ingestion and query pipelines, each scaling independently.

Query path:
API Gateway -> Semantic Cache -> Query Rewriter -> Hybrid Retriever -> Cross-Encoder Reranker -> Response

Ingestion path:
Document Upload -> Parse -> Chunk -> Embed -> Index -> ChromaDB
"""

import asyncio
import time
import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from .config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag.main")

router = APIRouter(prefix="/rag")


class RetrieveRequest(BaseModel):
    query: str
    crime_type: str = ""
    top_k: int = Field(default=5, ge=1, le=100)
    tenant_id: str = "default"
    transform_strategy: str = "auto"
    user_id: Optional[str] = None  # For retrieval_logs tracking
    session_id: Optional[str] = None  # For retrieval_logs tracking


class LawArticle(BaseModel):
    article_number: str
    law: str
    text: str
    relevance_score: float
    penalty_ar: Optional[str] = None
    summary: Optional[str] = None
    keywords: Any = ""
    chunk_type: Optional[str] = None
    parent_text: Optional[str] = None


class CitationValidationResult(BaseModel):
    valid: List[Dict[str, Any]] = Field(default_factory=list)
    invalid: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "PASSED"  # PASSED | FAILED
    validation_details: Dict[str, Any] = Field(default_factory=dict)


class RetrieveResponse(BaseModel):
    articles: List[LawArticle]
    cache_hit: bool = False
    cache_source: Optional[str] = None
    query_strategy: str = "none"
    latency_ms: float = 0.0
    citation_validation_status: Optional[CitationValidationResult] = None


class IndexRequest(BaseModel):
    articles: List[Dict[str, Any]]
    tenant_id: str = "default"
    async_ingest: bool = False
    user_id: Optional[str] = None  # For document ownership tracking
    case_id: Optional[str] = None  # For linking to cases


class IndexResponse(BaseModel):
    indexed: int
    articles_processed: int
    chunks_created: int
    collection: str
    tenant_id: str
    task_id: Optional[str] = None


class FaithfulnessRequest(BaseModel):
    query: str
    answer: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    tenant_id: str = "default"
    request_id: Optional[str] = None


class FaithfulnessResponse(BaseModel):
    faithfulness_score: Optional[float] = None
    has_citations: bool
    num_citations: int
    hallucination_risk: str
    evaluated: bool = True
    citation_coverage: float = 0.0
    uncertainty_detected: bool = False


@router.get("/health")
def health():
    """
    Liveness + readiness probe.
    Checks: ChromaDB connection, Redis cache, Celery worker.
    """
    redis_ok  = False
    chroma_ok = False
    celery_ok = False

    try:
        from services.common.cache import cache
        redis_ok = cache.enabled
    except Exception:
        redis_ok = False

    try:
        from .retriever import get_retriever_stats

        chroma_stats = get_retriever_stats()
        collection_name = chroma_stats.get("collection")

        document_count = chroma_stats.get("document_count")
        if document_count is None:
            document_count = chroma_stats.get("count")
        if document_count is None:
            document_count = chroma_stats.get("total_documents")

        chroma_connected = True
        chroma_collection_ready = bool(collection_name)
        chroma_has_data = (
            document_count is None
            or (isinstance(document_count, (int, float)) and document_count > 0)
        )
        chroma_ok = chroma_connected and chroma_collection_ready and chroma_has_data
    except Exception as e:
        chroma_stats = {"error": str(e)}
        chroma_connected = False
        chroma_collection_ready = False
        chroma_has_data = False
        chroma_ok = False

    try:
        from services.common.celery_app import celery_app
        insp      = celery_app.control.inspect(timeout=1)
        celery_ok = insp.active() is not None
    except Exception:
        celery_ok = False

    try:
        from .observability import get_metrics_summary
        metrics_data = get_metrics_summary()
    except Exception as e:
        metrics_data = {"error": str(e)}

    overall = "healthy" if chroma_ok else "degraded"
    return {
        "status": overall,
        "service": "rag",
        "version": "2.0.0",
        "vector_db": "chromadb",
        "chroma": "ok" if chroma_ok else "unavailable",
        "chroma_connected": chroma_connected,
        "chroma_collection_ready": chroma_collection_ready,
        "chroma_has_data": chroma_has_data,
        "chroma_stats": chroma_stats,
        "redis": "ok" if redis_ok else "unavailable",
        "celery": "ok" if celery_ok else "unavailable",
        "metrics": metrics_data,
    }


@router.get("/stats")
def get_stats():
    from .cache import get_cache_stats
    from .observability import get_metrics_summary
    from .retriever import get_retriever_stats

    return {
        "config": {
            "vector_db": f"chromadb_{config.chroma.client_type}",
            "chroma_client_type": config.chroma.client_type,
            "chroma_persist_directory": config.chroma.persist_directory if config.chroma.client_type == "persistent" else "",
            "chroma_cloud_tenant": config.chroma.cloud_tenant if config.chroma.client_type == "cloud" else "",
            "chroma_cloud_database": config.chroma.cloud_database if config.chroma.client_type == "cloud" else "",
            "chroma_collection": config.chroma.collection_name,
            "embedding_model": config.embedding.model_name,
            "chunk_size": config.chunking.chunk_size,
            "chunk_overlap": config.chunking.chunk_overlap,
            "reranker_enabled": config.reranker.enabled,
            "semantic_cache_enabled": config.cache.semantic_cache_enabled,
            "multi_tenant_enabled": config.multi_tenant.enabled,
            "hyde_enabled": config.query_transform.hyde_enabled,
            "rag_fusion_enabled": config.query_transform.rag_fusion_enabled,
        },
        "retriever": get_retriever_stats(),
        "cache": get_cache_stats(),
        "metrics": get_metrics_summary(),
    }


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(request: RetrieveRequest):
    start_time = time.time()
    enhanced_query = f"{request.crime_type}: {request.query}" if request.crime_type else request.query

    # Import citation validation
    from .citations import validate_citations

    try:
        from .cache import lookup
        cached = lookup(enhanced_query, request.tenant_id)

        if cached:
            latency = (time.time() - start_time) * 1000
            articles_data = cached.response.get("articles", [])

            # Validate citations for cached response
            citation_validation = validate_citations(
                articles_data,
                request.crime_type,
                request.tenant_id
            )

            return RetrieveResponse(
                articles=[LawArticle(**a) for a in articles_data],
                cache_hit=True,
                cache_source=cached.source,
                query_strategy="cache",
                latency_ms=round(latency, 2),
                citation_validation_status=CitationValidationResult(**citation_validation),
            )

    except Exception as e:
        logger.warning(f"Cache lookup failed: {e}")

    strategy_used = "none"
    queries = [enhanced_query]

    if request.transform_strategy != "none":
        try:
            from .query_transform import transform_query
            transform_result = await transform_query(enhanced_query, request.transform_strategy)
            queries = transform_result["queries"]
            strategy_used = transform_result["strategy"]
        except Exception as e:
            logger.warning(f"Query transform failed, using original query: {e}")

    all_results = []

    try:
        from .retriever import retrieve_and_validate

        loop = asyncio.get_running_loop()
        retrieval_tasks = []
        for q in queries:
            retrieval_tasks.append(
                loop.run_in_executor(None, retrieve_and_validate, q, max(request.top_k * 4, 20), request.tenant_id, None, request.crime_type)
            )

        for rv in await asyncio.gather(*retrieval_tasks):
            all_results.extend(rv.get("results", []))

    except Exception as e:
        logger.error(f"Hybrid retrieval failed: {e}")
        raise HTTPException(status_code=503, detail=f"Retrieval service unavailable: {e}")

    # Deduplicate by legal identity when metadata is available.
    # Fall back to the result ID so records with missing article metadata are
    # not incorrectly collapsed into one empty-string bucket. If duplicates
    # exist, keep the candidate with the strongest combined score.
    unique_by_key: Dict[Any, Any] = {}

    for result in all_results:
        metadata = result.metadata or {}
        article_number = str(metadata.get("article_number") or "").strip()
        law = str(metadata.get("law") or "").strip()

        if article_number:
            dedup_key = ("article", law, article_number)
        else:
            dedup_key = ("result", str(result.id))

        existing = unique_by_key.get(dedup_key)
        existing_score = float(getattr(existing, "combined_score", 0.0)) if existing else float("-inf")
        result_score = float(getattr(result, "combined_score", 0.0))

        if existing is None or result_score > existing_score:
            unique_by_key[dedup_key] = result

    unique_results = list(unique_by_key.values())

    reranker_applied = False

    try:
        from .reranker import rerank

        loop = asyncio.get_running_loop()
        unique_results = await loop.run_in_executor(
            None,
            rerank,
            request.query,
            unique_results,
            request.top_k,
        )
        reranker_applied = True
    except Exception as e:
        logger.warning("Reranking failed: %s", e)
        unique_results = unique_results[:request.top_k]

    articles = []

    for r in unique_results:
        meta = r.metadata or {}

        articles.append(
            LawArticle(
                article_number=str(meta.get("article_number", "Unknown")),
                law=str(meta.get("law", "Unknown")),
                text=r.text,
                relevance_score=float(r.combined_score),
                penalty_ar=meta.get("penalty_ar"),
                summary=meta.get("summary"),
                keywords=meta.get("keywords", ""),
                chunk_type=meta.get("chunk_type"),
                parent_text=getattr(r, "parent_text", None),
            )
        )

    latency = (time.time() - start_time) * 1000

    try:
        from .observability import record_retrieval, RetrievalMetric

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, record_retrieval, RetrievalMetric(
            timestamp=time.time(),
            query=request.query,
            tenant_id=request.tenant_id,
            strategy=strategy_used,
            num_results=len(articles),
            top_score=articles[0].relevance_score if articles else 0.0,
            avg_score=sum(a.relevance_score for a in articles) / len(articles) if articles else 0.0,
            cache_hit=False,
            latency_ms=latency,
            reranker_applied=reranker_applied,
            request_id=request.session_id,
            score_type="hybrid",
            query_transformed=strategy_used != "none",
        ))

    except Exception as e:
        logger.warning(f"Metrics recording failed: {e}")

    response_dict = {
        "articles": [a.dict() for a in articles],
    }

    if articles:
        try:
            from .cache import store
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, store, enhanced_query, response_dict, request.tenant_id)
        except Exception as e:
            logger.warning(f"Cache store failed: {e}")

    # Validate citations before returning
    articles_dicts = [a.dict() for a in articles]
    citation_validation = validate_citations(
        articles_dicts,
        request.crime_type,
        request.tenant_id
    )

    return RetrieveResponse(
        articles=articles,
        cache_hit=False,
        cache_source=None,
        query_strategy=strategy_used,
        latency_ms=round(latency, 2),
        citation_validation_status=CitationValidationResult(**citation_validation),
    )


@router.post("/index", response_model=IndexResponse)
async def index_articles(request: IndexRequest, background_tasks: BackgroundTasks):
    """Index law articles into ChromaDB."""

    if not request.articles:
        raise HTTPException(status_code=400, detail="No articles provided")

    if request.async_ingest:
        try:
            from .ingestion import get_celery_app

            celery_app = get_celery_app()

            if celery_app:
                task = celery_app.send_task(
                    "ingestion.index_articles",
                    args=[request.articles, request.tenant_id],
                    queue="ingestion",
                )

                return IndexResponse(
                    indexed=0,
                    articles_processed=len(request.articles),
                    chunks_created=0,
                    collection=config.chroma.collection_name,
                    tenant_id=request.tenant_id,
                    task_id=task.id,
                )

        except Exception as e:
            logger.warning(f"Celery queue failed, falling back to sync: {e}")

    try:
        from .ingestion import index_articles as ingest_articles

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, ingest_articles, request.articles, request.tenant_id
        )

        return IndexResponse(
            indexed=result.get("indexed", 0),
            articles_processed=result.get("articles_processed", 0),
            chunks_created=result.get("chunks_created", 0),
            collection=result.get("collection", config.chroma.collection_name),
            tenant_id=request.tenant_id,
        )

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index/document")
async def index_single_document(document: Dict[str, Any], tenant_id: str = "default"):
    """Index a single document into ChromaDB."""

    from .ingestion import index_articles as ingest_articles

    try:
        result = ingest_articles([document], tenant_id)
        return result

    except Exception as e:
        logger.error(f"Document indexing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/faithfulness", response_model=FaithfulnessResponse)
def check_faithfulness(request: FaithfulnessRequest):
    from .observability import check_faithfulness

    result = check_faithfulness(
        request.query,
        request.answer,
        request.citations,
        tenant_id=request.tenant_id,
        request_id=request.request_id,
    )

    return FaithfulnessResponse(
        faithfulness_score=result.faithfulness_score,
        has_citations=result.has_citations,
        num_citations=result.num_citations,
        hallucination_risk=result.hallucination_risk,
        evaluated=result.evaluated,
        citation_coverage=result.citation_coverage,
        uncertainty_detected=result.uncertainty_detected,
    )


@router.get("/tenants")
def list_tenants():
    """List all tenant namespaces in ChromaDB."""

    if not config.multi_tenant.enabled:
        return {
            "tenants": [],
            "multi_tenant_enabled": False,
        }

    try:
        from .retriever import _get_chroma

        client = _get_chroma()
        collections = client.list_collections()

        tenant_collections = []

        for collection in collections:
            name = collection.name if hasattr(collection, "name") else str(collection)

            if name.startswith(config.multi_tenant.namespace_prefix):
                tenant_collections.append(name)

        tenants = [
            name.replace(config.multi_tenant.namespace_prefix, "")
            for name in tenant_collections
        ]

        return {
            "tenants": tenants,
            "multi_tenant_enabled": True,
        }

    except Exception as e:
        return {
            "tenants": [],
            "error": str(e),
        }


@router.delete("/collections/{tenant_id}")
async def delete_collection(tenant_id: str):
    """Delete a tenant's collection (admin only)."""
    if not config.multi_tenant.enabled:
        raise HTTPException(status_code=400, detail="Multi-tenant mode not enabled")

    collection_name = f"{config.multi_tenant.namespace_prefix}{tenant_id}"

    try:
        from .retriever import _get_chroma

        client = _get_chroma()
        client.delete_collection(collection_name)

        return {
            "deleted": True,
            "collection": collection_name,
        }

    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


class ValidateCitationsRequest(BaseModel):
    articles: List[Dict[str, Any]]
    crime_type: str = ""
    tenant_id: str = "default"


@router.post("/validate-citations", response_model=CitationValidationResult)
async def validate_citations_endpoint(request: ValidateCitationsRequest):
    """Validate that cited articles exist in ChromaDB with matching crime_type."""
    from .citations import validate_citations

    result = validate_citations(
        request.articles,
        request.crime_type,
        request.tenant_id
    )

    return CitationValidationResult(**result)
#end