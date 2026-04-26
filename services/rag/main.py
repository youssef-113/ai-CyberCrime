"""RAG Service - Production Legal Retrieval Pipeline

Architecture: Separate ingestion and query pipelines, each scaling independently.
Query path (hot path): API Gateway -> Semantic Cache -> Query Rewriter -> Hybrid Retriever -> Cross-Encoder Reranker -> Response
Ingestion path (async): Document Upload -> Parse -> Chunk -> Embed (cached) -> Index -> Qdrant
"""
import time
import logging
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag.main")

app = FastAPI(title="RAG Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════
#  Request / Response Models
# ══════════════════════════════════════════════════════════════════════════

class RetrieveRequest(BaseModel):
    query: str
    crime_type: str = ""
    top_k: int = 5
    tenant_id: str = "default"
    transform_strategy: str = "auto"  # "auto" | "hyde" | "fusion" | "step_back" | "none"


class LawArticle(BaseModel):
    article_number: str
    law: str
    text: str
    relevance_score: float
    penalty_ar: Optional[str] = None
    summary: Optional[str] = None
    keywords: List[str] = []
    chunk_type: Optional[str] = None
    parent_text: Optional[str] = None  # parent chunk context


class RetrieveResponse(BaseModel):
    articles: List[LawArticle]
    cache_hit: bool = False
    cache_source: Optional[str] = None
    query_strategy: str = "none"
    latency_ms: float = 0.0


class IndexRequest(BaseModel):
    articles: List[Dict[str, Any]]
    tenant_id: str = "default"
    async_ingest: bool = False  # if True, queue via Celery


class IndexResponse(BaseModel):
    indexed: int
    articles_processed: int
    chunks_created: int
    collection: str
    tenant_id: str
    task_id: Optional[str] = None  # Celery task ID if async


class FaithfulnessRequest(BaseModel):
    query: str
    answer: str
    citations: List[Dict[str, Any]] = []


class FaithfulnessResponse(BaseModel):
    faithfulness_score: float
    has_citations: bool
    num_citations: int
    hallucination_risk: str  # "low" | "medium" | "high"


# ══════════════════════════════════════════════════════════════════════════
#  Health & Status Endpoints
# ══════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    """Health check with component status."""
    status = {
        "status": "healthy",
        "service": "rag",
        "version": "2.0.0",
    }

    # Check Qdrant
    try:
        from retriever import get_retriever_stats
        stats = get_retriever_stats()
        status["qdrant"] = stats
    except Exception as e:
        status["qdrant"] = {"error": str(e)}

    # Check cache
    try:
        from cache import get_cache_stats
        status["cache"] = get_cache_stats()
    except Exception as e:
        status["cache"] = {"error": str(e)}

    # Check observability
    try:
        from observability import get_metrics_summary
        status["metrics"] = get_metrics_summary()
    except Exception as e:
        status["metrics"] = {"error": str(e)}

    return status


@app.get("/stats")
def get_stats():
    """Detailed service statistics."""
    from cache import get_cache_stats
    from observability import get_metrics_summary
    from retriever import get_retriever_stats

    return {
        "config": {
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


# ══════════════════════════════════════════════════════════════════════════
#  Query Pipeline (Hot Path)
# ══════════════════════════════════════════════════════════════════════════

@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(request: RetrieveRequest):
    """Production retrieval pipeline.

    Flow: Semantic Cache -> Query Transform -> Hybrid Retrieve -> Rerank -> Response
    """
    start_time = time.time()
    enhanced_query = f"{request.crime_type}: {request.query}" if request.crime_type else request.query

    # Step 1: Check semantic cache
    cache_hit = False
    cache_source = None
    cached = None

    try:
        from cache import lookup
        cached = lookup(enhanced_query, request.tenant_id)
        if cached:
            cache_hit = True
            cache_source = cached.source
            latency = (time.time() - start_time) * 1000
            return RetrieveResponse(
                articles=[LawArticle(**a) for a in cached.response.get("articles", [])],
                cache_hit=True,
                cache_source=cache_source,
                query_strategy="cache",
                latency_ms=round(latency, 2),
            )
    except Exception as e:
        logger.warning(f"Cache lookup failed: {e}")

    # Step 2: Query transformation
    strategy_used = "none"
    queries = [enhanced_query]

    if request.transform_strategy != "none":
        try:
            from query_transform import transform_query
            transform_result = await transform_query(enhanced_query, request.transform_strategy)
            queries = transform_result["queries"]
            strategy_used = transform_result["strategy"]
        except Exception as e:
            logger.warning(f"Query transform failed, using original: {e}")

    # Step 3: Hybrid retrieval for each query variation
    all_results = []
    try:
        from retriever import hybrid_retrieve
        for q in queries:
            results = hybrid_retrieve(q, top_k=request.top_k * 2, tenant_id=request.tenant_id)
            all_results.extend(results)
    except Exception as e:
        logger.error(f"Hybrid retrieval failed: {e}")
        raise HTTPException(status_code=503, detail=f"Retrieval service unavailable: {e}")

    # Deduplicate by chunk ID
    seen_ids = set()
    unique_results = []
    for r in all_results:
        if r.id not in seen_ids:
            seen_ids.add(r.id)
            unique_results.append(r)

    # Step 4: Cross-encoder reranking
    try:
        from reranker import rerank
        unique_results = rerank(enhanced_query, unique_results, top_n=request.top_k)
    except Exception as e:
        logger.warning(f"Reranking failed, using raw scores: {e}")
        unique_results = unique_results[:request.top_k]

    # Step 5: Build response
    articles = []
    for r in unique_results:
        meta = r.metadata
        articles.append(LawArticle(
            article_number=meta.get("article_number", "Unknown"),
            law=meta.get("law", "Unknown"),
            text=r.text,
            relevance_score=r.combined_score,
            penalty_ar=meta.get("penalty_ar"),
            summary=meta.get("summary"),
            keywords=meta.get("keywords", []),
            chunk_type=meta.get("chunk_type"),
            parent_text=r.parent_text,
        ))

    latency = (time.time() - start_time) * 1000

    # Step 6: Record metrics
    try:
        from observability import record_retrieval, RetrievalMetric
        record_retrieval(RetrievalMetric(
            timestamp=time.time(),
            query=request.query,
            tenant_id=request.tenant_id,
            strategy=strategy_used,
            num_results=len(articles),
            top_score=articles[0].relevance_score if articles else 0.0,
            avg_score=sum(a.relevance_score for a in articles) / len(articles) if articles else 0.0,
            cache_hit=False,
            latency_ms=latency,
            reranker_applied=config.reranker.enabled,
            query_transformed=strategy_used != "none",
        ))
    except Exception as e:
        logger.warning(f"Metrics recording failed: {e}")

    # Step 7: Cache the result for future queries
    response_dict = {
        "articles": [a.dict() for a in articles],
    }
    try:
        from cache import store
        store(enhanced_query, response_dict, request.tenant_id)
    except Exception as e:
        logger.warning(f"Cache store failed: {e}")

    return RetrieveResponse(
        articles=articles,
        cache_hit=False,
        cache_source=None,
        query_strategy=strategy_used,
        latency_ms=round(latency, 2),
    )


# ══════════════════════════════════════════════════════════════════════════
#  Ingestion Pipeline (Async / Background)
# ══════════════════════════════════════════════════════════════════════════

@app.post("/index", response_model=IndexResponse)
async def index_articles(request: IndexRequest, background_tasks: BackgroundTasks):
    """Index law articles into Qdrant.

    By default runs synchronously. Set async_ingest=True to queue via Celery.
    """
    if not request.articles:
        raise HTTPException(status_code=400, detail="No articles provided")

    if request.async_ingest:
        # Queue via Celery
        try:
            from ingestion import get_celery_app
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
                    collection=config.qdrant.collection_name,
                    tenant_id=request.tenant_id,
                    task_id=task.id,
                )
        except Exception as e:
            logger.warning(f"Celery queue failed, falling back to sync: {e}")

    # Synchronous ingestion
    try:
        from ingestion import index_articles as ingest_articles
        result = ingest_articles(request.articles, request.tenant_id)
        return IndexResponse(
            indexed=result.get("indexed", 0),
            articles_processed=result.get("articles_processed", 0),
            chunks_created=result.get("chunks_created", 0),
            collection=result.get("collection", config.qdrant.collection_name),
            tenant_id=request.tenant_id,
        )
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/index/document")
async def index_single_document(document: Dict[str, Any], tenant_id: str = "default"):
    """Index a single document (async via background task)."""
    from ingestion import index_articles as ingest_articles
    try:
        result = ingest_articles([document], tenant_id)
        return result
    except Exception as e:
        logger.error(f"Document indexing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
#  Faithfulness / Guardrails
# ══════════════════════════════════════════════════════════════════════════

@app.post("/faithfulness", response_model=FaithfulnessResponse)
def check_faithfulness(request: FaithfulnessRequest):
    """Check faithfulness of generated output.

    RAG does NOT eliminate hallucinations. You still need:
    - Groundedness checks on outputs
    - Guardrails for sensitive domains
    - Enforcing citations for every part of the answer
    """
    from observability import check_faithfulness
    result = check_faithfulness(request.query, request.answer, request.citations)
    return FaithfulnessResponse(
        faithfulness_score=result.faithfulness_score,
        has_citations=result.has_citations,
        num_citations=result.num_citations,
        hallucination_risk=result.hallucination_risk,
    )


# ══════════════════════════════════════════════════════════════════════════
#  Multi-Tenant Management
# ══════════════════════════════════════════════════════════════════════════

@app.get("/tenants")
def list_tenants():
    """List all tenant namespaces in Qdrant."""
    if not config.multi_tenant.enabled:
        return {"tenants": [], "multi_tenant_enabled": False}

    try:
        from retriever import _get_qdrant
        client = _get_qdrant()
        collections = client.get_collections().collections
        tenant_collections = [
            c.name for c in collections
            if c.name.startswith(config.multi_tenant.namespace_prefix)
        ]
        tenants = [c.replace(config.multi_tenant.namespace_prefix, "") for c in tenant_collections]
        return {"tenants": tenants, "multi_tenant_enabled": True}
    except Exception as e:
        return {"tenants": [], "error": str(e)}


@app.delete("/tenants/{tenant_id}")
def delete_tenant(tenant_id: str):
    """Delete a tenant's entire namespace (isolated data)."""
    if not config.multi_tenant.enabled:
        raise HTTPException(status_code=400, detail="Multi-tenant mode is disabled")

    collection_name = f"{config.multi_tenant.namespace_prefix}{tenant_id}"
    try:
        from retriever import _get_qdrant
        client = _get_qdrant()
        client.delete_collection(collection_name)
        return {"deleted": True, "collection": collection_name}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
#  Startup & Run
# ══════════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup():
    """Initialize components on startup."""
    logger.info(f"RAG Service v2.0 starting...")
    logger.info(f"  Embedding model: {config.embedding.model_name}")
    logger.info(f"  Chunk size: {config.chunking.chunk_size} tokens, overlap: {config.chunking.chunk_overlap}")
    logger.info(f"  Reranker: {'enabled' if config.reranker.enabled else 'disabled'}")
    logger.info(f"  Semantic cache: {'enabled' if config.cache.semantic_cache_enabled else 'disabled'}")
    logger.info(f"  Multi-tenant: {'enabled' if config.multi_tenant.enabled else 'disabled'}")
    logger.info(f"  Query transforms: HyDE={'on' if config.query_transform.hyde_enabled else 'off'}, "
                f"Fusion={'on' if config.query_transform.rag_fusion_enabled else 'off'}, "
                f"Step-back={'on' if config.query_transform.step_back_enabled else 'off'}")
    logger.info(f"  LLM Provider: {config.query_transform.llm_provider}")
    logger.info(f"  Ollama: {config.ollama.model} @ {config.ollama.base_url}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
