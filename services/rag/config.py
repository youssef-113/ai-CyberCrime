"""RAG Service Configuration - Production Settings"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QdrantConfig:
    host: str = os.getenv("QDRANT_HOST", "qdrant")
    port: int = int(os.getenv("QDRANT_PORT", "6333"))
    collection_name: str = os.getenv("QDRANT_COLLECTION", "egyptian_law")
    vector_size: int = int(os.getenv("VECTOR_SIZE", "384"))  # all-MiniLM-L6-v2 dimension
    distance_metric: str = "Cosine"


@dataclass
class EmbeddingConfig:
    model_name: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    content_addressable: bool = True  # hash(model_id + text) to avoid re-embedding


@dataclass
class ChunkingConfig:
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "512"))  # tokens
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "200"))  # tokens
    separators: list = field(default_factory=lambda: ["\n\n## ", "\n\n### ", "\n\n", "\n", ". ", " "])
    parent_chunk_size: int = int(os.getenv("PARENT_CHUNK_SIZE", "1024"))  # parent chunks for context


@dataclass
class CacheConfig:
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    semantic_cache_enabled: bool = os.getenv("SEMANTIC_CACHE_ENABLED", "true").lower() == "true"
    semantic_cache_threshold: float = float(os.getenv("SEMANTIC_CACHE_THRESHOLD", "0.92"))
    semantic_cache_ttl: int = int(os.getenv("SEMANTIC_CACHE_TTL", "3600"))  # seconds
    faiss_cache_index_size: int = int(os.getenv("FAISS_CACHE_INDEX_SIZE", "10000"))


@dataclass
class RetrieverConfig:
    top_k: int = int(os.getenv("RETRIEVER_TOP_K", "20"))  # fetch more before reranking
    bm25_weight: float = float(os.getenv("BM25_WEIGHT", "0.3"))
    vector_weight: float = float(os.getenv("VECTOR_WEIGHT", "0.7"))
    min_vector_similarity: float = float(os.getenv("MIN_VECTOR_SIMILARITY", "0.5"))  # BM25 only boosts chunks above this


@dataclass
class RerankerConfig:
    model_name: str = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    enabled: bool = os.getenv("RERANKER_ENABLED", "true").lower() == "true"
    top_n: int = int(os.getenv("RERANKER_TOP_N", "5"))  # final results after reranking


@dataclass
class OllamaConfig:
    base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    timeout: int = int(os.getenv("OLLAMA_TIMEOUT", "60"))
    temperature: float = float(os.getenv("OLLAMA_TEMPERATURE", "0.3"))
    max_tokens: int = int(os.getenv("OLLAMA_MAX_TOKENS", "300"))


@dataclass
class QueryTransformConfig:
    hyde_enabled: bool = os.getenv("HYDE_ENABLED", "true").lower() == "true"
    rag_fusion_enabled: bool = os.getenv("RAG_FUSION_ENABLED", "true").lower() == "true"
    rag_fusion_queries: int = int(os.getenv("RAG_FUSION_QUERIES", "3"))
    step_back_enabled: bool = os.getenv("STEP_BACK_ENABLED", "false").lower() == "true"
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "claude-3-haiku-20240307")
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")  # "ollama" | "anthropic" | "openai"


@dataclass
class IngestionConfig:
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/1")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/2")
    batch_size: int = int(os.getenv("INGESTION_BATCH_SIZE", "100"))


@dataclass
class ObservabilityConfig:
    enabled: bool = os.getenv("OBSERVABILITY_ENABLED", "true").lower() == "true"
    faithfulness_threshold: float = float(os.getenv("FAITHFULNESS_THRESHOLD", "0.7"))
    log_retrieval_metrics: bool = True


@dataclass
class MultiTenantConfig:
    enabled: bool = os.getenv("MULTI_TENANT_ENABLED", "true").lower() == "true"
    namespace_prefix: str = os.getenv("TENANT_NAMESPACE_PREFIX", "tenant_")


@dataclass
class RAGConfig:
    qdrant: QdrantConfig = field(default_factory=QdrantConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    retriever: RetrieverConfig = field(default_factory=RetrieverConfig)
    reranker: RerankerConfig = field(default_factory=RerankerConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    query_transform: QueryTransformConfig = field(default_factory=QueryTransformConfig)
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    multi_tenant: MultiTenantConfig = field(default_factory=MultiTenantConfig)


config = RAGConfig()
