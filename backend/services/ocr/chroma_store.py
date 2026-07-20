from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

from models import OCRResponse

logger = logging.getLogger("ocr.chroma")

CHROMA_AVAILABLE = False
try:
    import chromadb
    from sentence_transformers import SentenceTransformer

    CHROMA_AVAILABLE = True
except ImportError:
    logger.warning("chromadb/sentence-transformers not installed — vector store disabled")

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "evidence")

_client = None
_collection = None
_embedder = None


def _ensure_connection() -> None:
    global _client, _collection, _embedder
    if _collection is not None:
        return
    if not CHROMA_AVAILABLE:
        return
    try:
        _client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        _collection = _client.get_or_create_collection(CHROMA_COLLECTION)
        _embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        logger.info("ChromaDB connected — collection=%s", CHROMA_COLLECTION)
    except Exception as exc:
        logger.warning("ChromaDB HTTP client failed (%s) — trying in-memory", exc)
        try:
            _client = chromadb.EphemeralClient()
            _collection = _client.get_or_create_collection(CHROMA_COLLECTION)
            _embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            logger.info("ChromaDB in-memory — collection=%s", CHROMA_COLLECTION)
        except Exception as exc2:
            logger.warning("ChromaDB unavailable (%s) — continuing without indexing", exc2)
            _client = None
            _collection = None


def is_available() -> bool:
    return _collection is not None


def store_ocr_result(
    ocr_response: OCRResponse,
    case_id: str = "",
    document_id: str = "",
    page_number: int = 1,
) -> bool:
    _ensure_connection()
    if _collection is None or _embedder is None:
        return False

    try:
        text = ocr_response.clean_text or ocr_response.raw_text
        if not text.strip():
            return False

        embedding = _embedder.encode(text).tolist()

        doc_id = f"{document_id or 'doc'}_p{page_number}"
        metadata = {
            "case_id": case_id or "",
            "document_id": document_id or "",
            "page_number": page_number,
            "language": ocr_response.document_language,
            "crime_type": ocr_response.crime_type,
            "confidence": ocr_response.confidence,
            "entities": str(ocr_response.entities.model_dump()),
            "timestamp": time.time(),
        }

        _collection.add(
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata],
            ids=[doc_id],
        )
        logger.info("ChromaDB stored: %s", doc_id)
        return True

    except Exception as exc:
        logger.warning("ChromaDB store failed (%s) — continuing without indexing", exc)
        return False


def search_similar(
    query: str,
    n_results: int = 5,
    filter_criteria: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    _ensure_connection()
    if _collection is None or _embedder is None:
        return []

    try:
        query_embedding = _embedder.encode(query).tolist()
        results = _collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_criteria,
        )

        items = []
        for i in range(len(results["ids"][0])):
            items.append({
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if results.get("distances") else None,
            })
        return items

    except Exception as exc:
        logger.warning("ChromaDB search failed: %s", exc)
        return []


def delete_document(doc_id: str) -> bool:
    _ensure_connection()
    if _collection is None:
        return False
    try:
        _collection.delete(ids=[doc_id])
        return True
    except Exception as exc:
        logger.warning("ChromaDB delete failed: %s", exc)
        return False


def health_check() -> Dict[str, Any]:
    _ensure_connection()
    if _collection is None:
        return {"connected": False, "available": CHROMA_AVAILABLE}
    try:
        count = _collection.count()
        return {
            "connected": True,
            "available": CHROMA_AVAILABLE,
            "collection": CHROMA_COLLECTION,
            "document_count": count,
        }
    except Exception as exc:
        return {"connected": False, "available": CHROMA_AVAILABLE, "error": str(exc)}
