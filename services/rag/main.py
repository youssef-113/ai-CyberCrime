"""RAG Service - Production Legal Retrieval Pipeline

Architecture: Separate ingestion and query pipelines, each scaling independently.

Query path:
API Gateway -> Semantic Cache -> Query Rewriter -> Hybrid Retriever -> Cross-Encoder Reranker -> Response

Ingestion path:
Document Upload -> Parse -> Chunk -> Embed -> Index -> ChromaDB
"""

import time
import logging
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag.main")

app = FastAPI(title="RAG Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RetrieveRequest(BaseModel):
    query: str
    crime_type: str = ""
    top_k: int = 5
    tenant_id: str = "default"
    transform_strategy: str = "auto"


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
    valid: List[Dict[str, Any]] = []
    invalid: List[Dict[str, Any]] = []
    status: str = "PASSED"  # PASSED | FAILED
    validation_details: Dict[str, Any] = {}


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
    citations: List[Dict[str, Any]] = []


class FaithfulnessResponse(BaseModel):
    faithfulness_score: float
    has_citations: bool
    num_citations: int
    hallucination_risk: str


@app.get("/health")
def health():
    status = {
        "status": "healthy",
        "service": "rag",
        "version": "2.0.0",
        "vector_db": "chromadb",
    }

    try:
        from .retriever import get_retriever_stats
        status["chroma"] = get_retriever_stats()
    except Exception as e:
        status["chroma"] = {"error": str(e)}

    try:
        from .cache import get_cache_stats
        status["cache"] = get_cache_stats()
    except Exception as e:
        status["cache"] = {"error": str(e)}

    try:
        from .observability import get_metrics_summary
        status["metrics"] = get_metrics_summary()
    except Exception as e:
        status["metrics"] = {"error": str(e)}

    return status


@app.get("/stats")
def get_stats():
    from .cache import get_cache_stats
    from .observability import get_metrics_summary
    from .retriever import get_retriever_stats

    return {
        "config": {
            "vector_db": "chromadb",
            "chroma_host": config.chroma.host,
            "chroma_port": config.chroma.port,
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


@app.post("/retrieve", response_model=RetrieveResponse)
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
        from .retriever import hybrid_retrieve

        for q in queries:
            results = hybrid_retrieve(
                q,
                top_k=request.top_k * 2,
                tenant_id=request.tenant_id,
            )
            all_results.extend(results)

    except Exception as e:
        logger.error(f"Hybrid retrieval failed: {e}")
        raise HTTPException(status_code=503, detail=f"Retrieval service unavailable: {e}")

    seen_ids = set()
    seen_articles = set()
    unique_results = []

    for r in all_results:
        article_num = r.metadata.get("article_number", "") if r.metadata else ""
        if article_num not in seen_articles:
            seen_ids.add(r.id)
            seen_articles.add(article_num)
            unique_results.append(r)

    try:
       from .reranker import rerank
       unique_results = rerank(request.query, unique_results, top_n=request.top_k)
    except Exception as e:
       logger.warning(f"Reranking failed: {e}")
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

        record_retrieval(
            RetrievalMetric(
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
            )
        )

    except Exception as e:
        logger.warning(f"Metrics recording failed: {e}")

    response_dict = {
        "articles": [a.dict() for a in articles],
    }

    try:
        from .cache import store
        store(enhanced_query, response_dict, request.tenant_id)
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


@app.post("/index", response_model=IndexResponse)
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

        result = ingest_articles(request.articles, request.tenant_id)

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


@app.post("/index/document")
async def index_single_document(document: Dict[str, Any], tenant_id: str = "default"):
    """Index a single document into ChromaDB."""

    from .ingestion import index_articles as ingest_articles

    try:
        result = ingest_articles([document], tenant_id)
        return result

    except Exception as e:
        logger.error(f"Document indexing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/faithfulness", response_model=FaithfulnessResponse)
def check_faithfulness(request: FaithfulnessRequest):
    from .observability import check_faithfulness

    result = check_faithfulness(
        request.query,
        request.answer,
        request.citations,
    )

    return FaithfulnessResponse(
        faithfulness_score=result.faithfulness_score,
        has_citations=result.has_citations,
        num_citations=result.num_citations,
        hallucination_risk=result.hallucination_risk,
    )


@app.get("/tenants")
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


@app.delete("/collections/{tenant_id}")
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


@app.post("/validate-citations", response_model=CitationValidationResult)
async def validate_citations_endpoint(request: ValidateCitationsRequest):
    """Validate that cited articles exist in ChromaDB with matching crime_type."""
    from .citations import validate_citations

    result = validate_citations(
        request.articles,
        request.crime_type,
        request.tenant_id
    )

    return CitationValidationResult(**result)


@app.on_event("startup")
async def startup():
    logger.info("RAG Service v2.0 starting...")
    logger.info(f"  Vector DB: ChromaDB")
    logger.info(f"  Chroma: {config.chroma.collection_name} @ {config.chroma.host}:{config.chroma.port}")
    logger.info(f"  Embedding model: {config.embedding.model_name}")
    logger.info(f"  Chunk size: {config.chunking.chunk_size} tokens, overlap: {config.chunking.chunk_overlap}")
    logger.info(f"  Reranker: {'enabled' if config.reranker.enabled else 'disabled'}")
    logger.info(f"  Semantic cache: {'enabled' if config.cache.semantic_cache_enabled else 'disabled'}")
    logger.info(f"  Multi-tenant: {'enabled' if config.multi_tenant.enabled else 'disabled'}")
    logger.info(
        f"  Query transforms: "
        f"HyDE={'on' if config.query_transform.hyde_enabled else 'off'}, "
        f"Fusion={'on' if config.query_transform.rag_fusion_enabled else 'off'}, "
        f"Step-back={'on' if config.query_transform.step_back_enabled else 'off'}"
    )
    logger.info(f"  LLM Provider: {config.query_transform.llm_provider}")
    logger.info(f"  Ollama: {config.ollama.model} @ {config.ollama.base_url}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)
