"""Validated RAG service configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field
from typing import List


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean; got {raw!r}")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(raw) if raw is not None else default
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer; got {raw!r}") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    try:
        return float(raw) if raw is not None else default
    except ValueError as exc:
        raise ValueError(f"{name} must be a number; got {raw!r}") from exc


@dataclass
class ChromaConfig:
    client_type: str = os.getenv("CHROMA_CLIENT_TYPE", "persistent")
    api_key: str = os.getenv("CHROMA_API_KEY", "")
    cloud_tenant: str = os.getenv("CHROMA_CLOUD_TENANT", "")
    cloud_database: str = os.getenv("CHROMA_CLOUD_DATABASE", "egyptian_law")
    collection_name: str = os.getenv("CHROMA_COLLECTION", "egyptian_law")
    persist_directory: str = os.getenv("CHROMA_PERSIST_DIR", "data/law_db")

    def __post_init__(self) -> None:
        if self.client_type not in {"persistent", "cloud"}:
            raise ValueError("CHROMA_CLIENT_TYPE must be 'persistent' or 'cloud'")
        if self.client_type == "cloud" and not all(
            [self.api_key, self.cloud_tenant, self.cloud_database]
        ):
            raise ValueError("Cloud Chroma requires API key, tenant, and database")


@dataclass
class EmbeddingConfig:
    model_name: str = os.getenv("EMBEDDING_MODEL_NAME", "intfloat/multilingual-e5-small")
    query_prefix: str = os.getenv("EMBEDDING_QUERY_PREFIX", "query: ")
    passage_prefix: str = os.getenv("EMBEDDING_PASSAGE_PREFIX", "passage: ")
    content_addressable: bool = _env_bool("EMBEDDING_CONTENT_ADDRESSABLE", True)


@dataclass
class ChunkingConfig:
    chunk_size: int = _env_int("CHUNK_SIZE", 512)
    chunk_overlap: int = _env_int("CHUNK_OVERLAP", 200)
    separators: List[str] = field(
        default_factory=lambda: ["\n\n## ", "\n\n### ", "\n\n", "\n", ". ", " "]
    )
    parent_chunk_size: int = _env_int("PARENT_CHUNK_SIZE", 1024)

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError("CHUNK_SIZE must be greater than zero")
        if not 0 <= self.chunk_overlap < self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be >= 0 and smaller than CHUNK_SIZE")
        if self.parent_chunk_size <= self.chunk_size:
            raise ValueError("PARENT_CHUNK_SIZE must be greater than CHUNK_SIZE")
        if self.chunk_overlap >= self.parent_chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than PARENT_CHUNK_SIZE")


@dataclass
class CacheConfig:
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    semantic_cache_enabled: bool = _env_bool("SEMANTIC_CACHE_ENABLED", False)
    semantic_cache_threshold: float = _env_float("SEMANTIC_CACHE_THRESHOLD", 0.92)
    semantic_cache_ttl: int = _env_int("SEMANTIC_CACHE_TTL", 3600)
    faiss_cache_index_size: int = _env_int("FAISS_CACHE_INDEX_SIZE", 10000)
    redis_retry_interval_seconds: int = _env_int("CACHE_REDIS_RETRY_SECONDS", 60)

    def __post_init__(self) -> None:
        if not 0 <= self.semantic_cache_threshold <= 1:
            raise ValueError("SEMANTIC_CACHE_THRESHOLD must be between 0 and 1")
        if self.semantic_cache_ttl <= 0 or self.faiss_cache_index_size <= 0:
            raise ValueError("Cache TTL and FAISS index size must be greater than zero")


@dataclass
class RetrieverConfig:
    top_k: int = _env_int("RETRIEVER_TOP_K", 20)
    bm25_weight: float = _env_float("BM25_WEIGHT", 0.3)
    vector_weight: float = _env_float("VECTOR_WEIGHT", 0.7)
    min_vector_similarity: float = _env_float("MIN_VECTOR_SIMILARITY", 0.0)

    def __post_init__(self) -> None:
        if self.top_k <= 0:
            raise ValueError("RETRIEVER_TOP_K must be greater than zero")
        if self.bm25_weight < 0 or self.vector_weight < 0:
            raise ValueError("Retriever weights cannot be negative")
        total = self.bm25_weight + self.vector_weight
        if total <= 0:
            raise ValueError("At least one retriever weight must be positive")
        self.bm25_weight /= total
        self.vector_weight /= total
        if not 0 <= self.min_vector_similarity <= 1:
            raise ValueError("MIN_VECTOR_SIMILARITY must be between 0 and 1")


@dataclass
class RerankerConfig:
    model_name: str = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    enabled: bool = _env_bool("RERANKER_ENABLED", False)
    top_n: int = _env_int("RERANKER_TOP_N", 5)


@dataclass
class OllamaConfig:
    base_url: str = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    timeout: int = _env_int("OLLAMA_TIMEOUT", 5)
    temperature: float = _env_float("OLLAMA_TEMPERATURE", 0.3)
    max_tokens: int = _env_int("OLLAMA_MAX_TOKENS", 300)


@dataclass
class QueryTransformConfig:
    hyde_enabled: bool = _env_bool("HYDE_ENABLED", False)
    rag_fusion_enabled: bool = _env_bool("RAG_FUSION_ENABLED", False)
    rag_fusion_queries: int = _env_int("RAG_FUSION_QUERIES", 3)
    step_back_enabled: bool = _env_bool("STEP_BACK_ENABLED", False)
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")

    def __post_init__(self) -> None:
        if self.llm_provider not in {"ollama", "groq"}:
            raise ValueError("LLM_PROVIDER must be 'ollama' or 'groq'")


@dataclass
class IngestionConfig:
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/1")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/2")
    batch_size: int = _env_int("INGESTION_BATCH_SIZE", 100)
    embedding_batch_size: int = _env_int("EMBEDDING_BATCH_SIZE", 32)
    embedding_l1_cache_max_items: int = _env_int("EMBEDDING_L1_CACHE_MAX_ITEMS", 50000)
    redis_retry_interval_seconds: int = _env_int("EMBEDDING_REDIS_RETRY_SECONDS", 60)

    def __post_init__(self) -> None:
        for name, value in {
            "INGESTION_BATCH_SIZE": self.batch_size,
            "EMBEDDING_BATCH_SIZE": self.embedding_batch_size,
            "EMBEDDING_L1_CACHE_MAX_ITEMS": self.embedding_l1_cache_max_items,
            "EMBEDDING_REDIS_RETRY_SECONDS": self.redis_retry_interval_seconds,
        }.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")


@dataclass
class ObservabilityConfig:
    enabled: bool = _env_bool("OBSERVABILITY_ENABLED", False)
    faithfulness_threshold: float = _env_float("FAITHFULNESS_THRESHOLD", 0.7)
    log_retrieval_metrics: bool = _env_bool("LOG_RETRIEVAL_METRICS", True)
    low_retrieval_score_threshold: float = _env_float("LOW_RETRIEVAL_SCORE_THRESHOLD", 0.25)
    high_latency_threshold_ms: float = _env_float("HIGH_LATENCY_THRESHOLD_MS", 5000.0)
    alert_cooldown_seconds: int = _env_int("ALERT_COOLDOWN_SECONDS", 300)


@dataclass
class MultiTenantConfig:
    enabled: bool = _env_bool("MULTI_TENANT_ENABLED", False)
    namespace_prefix: str = os.getenv("TENANT_NAMESPACE_PREFIX", "tenant_")


@dataclass
class RAGConfig:
    chroma: ChromaConfig = field(default_factory=ChromaConfig)
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


config = RAGConfig() #end
