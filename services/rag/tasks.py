"""Celery tasks for async RAG processing"""
import logging
from typing import Dict, Any, List
from celery import Task
from services.common.celery_app import celery_app
import asyncio

logger = logging.getLogger("rag.tasks")


class RAGTask(Task):
    """Base task for RAG operations with error handling"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f"RAG task {task_id} failed: {str(exc)}")
        super().on_failure(exc, task_id, args, kwargs, einfo)


@celery_app.task(
    bind=True,
    base=RAGTask,
    name="services.rag.tasks.index_documents_async",
    max_retries=3,
    default_retry_delay=60
)
def index_documents_async(self, documents: List[Dict[str, Any]], tenant_id: str = "default") -> Dict[str, Any]:
    """
    Index documents asynchronously in ChromaDB
    
    Args:
        documents: List of documents to index
        tenant_id: Tenant namespace for isolation
    
    Returns:
        Indexing result
    """
    try:
        from .config import config
        from .ingestion import ingest_documents
        
        result = ingest_documents(documents, tenant_id)
        
        return {
            "status": "success",
            "indexed_count": len(documents),
            "tenant_id": tenant_id,
        }
    except Exception as e:
        logger.error(f"Document indexing failed: {str(e)}")
        raise


@celery_app.task(
    bind=True,
    base=RAGTask,
    name="services.rag.tasks.cache_warmup",
    max_retries=2,
    default_retry_delay=30
)
def cache_warmup(self, queries: List[str]) -> Dict[str, Any]:
    """
    Warm up cache with common queries
    
    Args:
        queries: List of common queries to pre-cache
    
    Returns:
        Cache warmup result
    """
    try:
        from .main import retrieve
        from services.common.cache import cache
        
        warmed_count = 0
        for query in queries:
            try:
                result = retrieve(query, crime_type="", top_k=5)
                cache_key = f"rag:query:{hash(query)}"
                cache.set(cache_key, result, ttl=3600)
                warmed_count += 1
            except Exception as e:
                logger.warning(f"Failed to warm up cache for query: {query[:50]}...")
        
        return {
            "status": "success",
            "warmed_count": warmed_count,
        }
    except Exception as e:
        logger.error(f"Cache warmup failed: {str(e)}")
        raise
