"""Hybrid Retriever - ChromaDB Vector Search + BM25-like Keyword Boost"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import numpy as np

from .config import config

logger = logging.getLogger("rag.retriever")

_chroma_client = None
_embedding_model = None


def _get_chroma():
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


def _get_embedding_model():
    global _embedding_model

    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(config.embedding.model_name)

    return _embedding_model


@dataclass
class RetrievalResult:
    id: str
    text: str
    metadata: Dict[str, Any]
    vector_score: float = 0.0
    bm25_score: float = 0.0
    combined_score: float = 0.0
    parent_text: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "text": self.parent_text or self.text,
            "child_text": self.text if self.parent_text else None,
            "metadata": self.metadata,
            "vector_score": round(self.vector_score, 4),
            "bm25_score": round(self.bm25_score, 4),
            "combined_score": round(self.combined_score, 4),
        }


def _get_collection(collection_name: str):
    client = _get_chroma()
    return client.get_or_create_collection(name=collection_name)


def _fetch_parent_text(collection, parent_id: str) -> Optional[str]:
    if not parent_id:
        return None

    try:
        result = collection.get(ids=[parent_id], include=["documents", "metadatas"])
        documents = result.get("documents") or []
        if documents:
            return documents[0]
    except Exception as e:
        logger.warning(f"Failed to fetch parent chunk {parent_id}: {e}")

    return None


def _vector_search(
    query: str,
    collection_name: str,
    top_k: int,
    tenant_id: str = "default",
) -> List[RetrievalResult]:

    collection = _get_collection(collection_name)
    model = _get_embedding_model()

    prefixed_query = f"{config.embedding.query_prefix}{query}"
    query_vec = model.encode([prefixed_query], normalize_embeddings=True).astype(np.float32)[0].tolist()

    query_kwargs = {
        "query_embeddings": [query_vec],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }

    if config.multi_tenant.enabled and tenant_id != "default":
        query_kwargs["where"] = {"tenant_id": tenant_id}

    try:
        result = collection.query(**query_kwargs)
    except Exception as e:
        logger.error(f"ChromaDB vector search failed: {e}")
        return []

    raw_ids = result.get("ids", [])
    raw_docs = result.get("documents", [])
    raw_meta = result.get("metadatas", [])
    raw_dist = result.get("distances", [])

    ids = raw_ids[0] if raw_ids and isinstance(raw_ids[0], list) else raw_ids
    documents = raw_docs[0] if raw_docs and isinstance(raw_docs[0], list) else raw_docs
    metadatas = raw_meta[0] if raw_meta and isinstance(raw_meta[0], list) else raw_meta
    distances = raw_dist[0] if raw_dist and isinstance(raw_dist[0], list) else raw_dist

    retrieval_results = []

    for idx, chunk_id in enumerate(ids):
        text = documents[idx] if idx < len(documents) else ""
        metadata = metadatas[idx] if idx < len(metadatas) and metadatas[idx] else {}
        distance = distances[idx] if idx < len(distances) else 999.0

        vector_score = 1.0 / (1.0 + float(distance))

        parent_text = None
        if metadata.get("chunk_type") == "child" and metadata.get("parent_id"):
            parent_text = _fetch_parent_text(collection, metadata.get("parent_id"))

        retrieval_results.append(
            RetrievalResult(
                id=str(chunk_id),
                text=text,
                metadata=metadata,
                vector_score=vector_score,
                parent_text=parent_text,
            )
        )

    logger.info(f"Vector search returned {len(retrieval_results)} results")
    return retrieval_results


def _keywords_to_set(keywords: Any) -> set:
    if not keywords:
        return set()

    if isinstance(keywords, list):
        return {str(k).lower().strip() for k in keywords if str(k).strip()}

    if isinstance(keywords, str):
        # Handle stringified list like "['تشهير', 'بيانات']"
        cleaned = keywords.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
        return {k.lower().strip() for k in cleaned.replace(",", " ").split() if k.strip()}

    return set()


def _bm25_like_scores(query: str, results: List[RetrievalResult]) -> Dict[str, float]:
    query_terms = _tokenize(query)
    scores = {}

    if not query_terms:
        return scores

    for result in results:
        full_text = ((result.text or "") + " " + (result.parent_text or ""))
        text_terms = _tokenize(full_text)
        keyword_terms = _tokenize(' '.join(_keywords_to_set(result.metadata.get("keywords", ""))))

        overlap = len(query_terms & text_terms)
        overlap += len(query_terms & keyword_terms) * 2

        if overlap > 0:
            scores[result.id] = overlap / max(len(query_terms), 1)

    return scores


_ARABIC_NORMALIZE_MAP = {
    '\u0622': '\u0627',  # آ → ا
    '\u0623': '\u0627',  # أ → ا
    '\u0625': '\u0627',  # إ → ا
    '\u0649': '\u064A',  # ى → ي
    '\u0629': '\u0647',  # ة → ه
    '\u064B': '', '\u064C': '', '\u064D': '', '\u064E': '',
    '\u064F': '', '\u0650': '', '\u0651': '', '\u0652': '',  # Remove diacritics
}

_ARABIC_PREFIXES = ['\u0627\u0644', '\u0648', '\u0641', '\u0628', '\u0643', '\u0644']  # ال, و, ف, ب, ك, ل


def _normalize_arabic(text: str) -> str:
    res = []
    for c in text:
        if c in _ARABIC_NORMALIZE_MAP:
            c = _ARABIC_NORMALIZE_MAP[c]
        if c:
            res.append(c)
    return ''.join(res)


def _strip_arabic_prefix(word: str) -> str:
    """Strip common Arabic prefixes like ال, و, ف, ب."""
    for prefix in _ARABIC_PREFIXES:
        if word.startswith(prefix) and len(word) > len(prefix):
            return word[len(prefix):]
    return word


def _tokenize(text: str) -> set:
    norm = _normalize_arabic(text.lower().strip())
    tokens = set()
    for t in norm.split():
        t = t.strip()
        if not t:
            continue
        tokens.add(t)
        stripped = _strip_arabic_prefix(t)
        if stripped != t:
            tokens.add(stripped)
    return tokens


def _count_arabic_chars(text: str) -> int:
    return sum(1 for c in text if '\u0600' <= c <= '\u06FF' or '\u0750' <= c <= '\u077F' or '\u08A0' <= c <= '\u08FF' or '\uFB50' <= c <= '\uFDFF' or '\uFE70' <= c <= '\uFEFF')


def _keyword_search_all(query: str, collection_name: str, top_k: int, tenant_id: str) -> List[RetrievalResult]:
    """Full keyword search across ALL articles in ChromaDB.
    
    Bypasses vector search entirely — fetches every chunk and scores by
    keyword/term overlap.  Needed for Arabic queries where the English-only
    embedding model produces random similarity scores.
    """
    collection = _get_collection(collection_name)
    total = collection.count()
    if total == 0:
        return []

    all_data = collection.get(
        include=["documents", "metadatas"],
        limit=total,
    )
    ids = all_data.get("ids", [])
    documents = all_data.get("documents", []) or []
    metadatas = all_data.get("metadatas", []) or []

    query_terms = _tokenize(query)
    if not query_terms:
        return []

    scored = []
    for idx, chunk_id in enumerate(ids):
        text = documents[idx] if idx < len(documents) else ""
        meta = metadatas[idx] if idx < len(metadatas) and metadatas[idx] else {}

        # Score by term overlap in text + keywords (keywords weighted 3x)
        text_terms = _tokenize(text) if text else set()
        kw_terms = _tokenize(' '.join(_keywords_to_set(meta.get("keywords", ""))))
        score = len(query_terms & text_terms)
        score += len(query_terms & kw_terms) * 3

        if score > 0:
            parent_text = None
            if meta.get("chunk_type") == "child" and meta.get("parent_id"):
                parent_text = _fetch_parent_text(collection, meta.get("parent_id"))

            scored.append(RetrievalResult(
                id=str(chunk_id),
                text=text,
                metadata=meta,
                combined_score=float(score) / float(len(query_terms)),
                parent_text=parent_text,
            ))

    scored.sort(key=lambda r: r.combined_score, reverse=True)
    logger.info(f"Keyword search: {len(scored)} of {total} chunks matched (arabic query)")
    return scored[:top_k]


def hybrid_retrieve(
    query: str,
    top_k: int = None,
    tenant_id: str = "default",
    collection_name: str = None,
) -> List[RetrievalResult]:

    top_k = top_k or config.retriever.top_k
    collection_name = collection_name or config.chroma.collection_name

    if config.multi_tenant.enabled and tenant_id != "default":
        collection_name = f"{config.multi_tenant.namespace_prefix}{tenant_id}"

    # multilingual-e5-small handles Arabic natively, so use vector search for all queries
    vector_results = _vector_search(
        query=query,
        collection_name=collection_name,
        top_k=top_k,
        tenant_id=tenant_id,
    )

    if not vector_results:
        return []

    bm25_scores = _bm25_like_scores(query, vector_results)

    vec_weight = config.retriever.vector_weight
    bm25_weight = config.retriever.bm25_weight

    for result in vector_results:
        bm25 = bm25_scores.get(result.id, 0.0)
        result.bm25_score = bm25
        result.combined_score = (vec_weight * result.vector_score) + (bm25_weight * bm25)

    vector_results.sort(key=lambda r: r.combined_score, reverse=True)

    logger.info(f"Hybrid retrieve returned {len(vector_results[:top_k])} results")
    return vector_results[:top_k]


def retrieve_and_validate(
    query: str,
    top_k: int = None,
    tenant_id: str = "default",
    collection_name: str = None,
    crime_type: str = "",
) -> dict:
    """Run hybrid retrieve and validate returned articles against citation DB.

    Returns dict: { "results": [RetrievalResult], "validation": {..} }
    """
    results = hybrid_retrieve(query=query, top_k=top_k, tenant_id=tenant_id, collection_name=collection_name)

    # Convert to article-like dicts for validation
    articles = []
    for r in results:
        meta = r.metadata or {}
        articles.append({
            "article_number": meta.get("article_number") or meta.get("id") or "",
            "law": meta.get("law", ""),
            "text": r.text,
        })

    # Validate citations
    try:
        from .citations import validate_citations
        validation = validate_citations(articles, crime_type, tenant_id)
    except Exception as e:
        validation = {"status": "FAILED", "error": str(e), "valid": [], "invalid": []}

    return {"results": results, "validation": validation}

def get_retriever_stats() -> Dict[str, Any]:
    stats = {
        "vector_db": f"chromadb_{config.chroma.client_type}",
        "client_type": config.chroma.client_type,
        "persist_directory": config.chroma.persist_directory if config.chroma.client_type == "persistent" else "",
        "collection": config.chroma.collection_name,
    }

    try:
        client = _get_chroma()
        collection = client.get_or_create_collection(name=config.chroma.collection_name)

        stats["document_count"] = collection.count()
        stats["status"] = "ok"

    except Exception as e:
        stats["status"] = "error"
        stats["error"] = str(e)

    return stats