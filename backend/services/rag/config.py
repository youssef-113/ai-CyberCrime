"""RAG Service Configuration - Simple Test Settings"""
import os
from dataclasses import dataclass, field


@dataclass
class ChromaConfig:
    client_type: str = os.getenv("CHROMA_CLIENT_TYPE", "persistent")  # "persistent" | "cloud"
    api_key: str = os.getenv("CHROMA_API_KEY", "")
    cloud_tenant: str = os.getenv("CHROMA_CLOUD_TENANT", "")
    cloud_database: str = os.getenv("CHROMA_CLOUD_DATABASE", "egyptian_law")
    collection_name: str = os.getenv("CHROMA_COLLECTION", "egyptian_law")
    persist_directory: str = os.getenv("CHROMA_PERSIST_DIR", "data/law_db")


@dataclass
class EmbeddingConfig:
    model_name: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    content_addressable: bool = True


@dataclass
class ChunkingConfig:
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "512"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "200"))
    separators: list = field(default_factory=lambda: ["\n\n## ", "\n\n### ", "\n\n", "\n", ". ", " "])
    parent_chunk_size: int = int(os.getenv("PARENT_CHUNK_SIZE", "1024"))


@dataclass
class CacheConfig:
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    semantic_cache_enabled: bool = os.getenv("SEMANTIC_CACHE_ENABLED", "false").lower() == "true"
    semantic_cache_threshold: float = float(os.getenv("SEMANTIC_CACHE_THRESHOLD", "0.92"))
    semantic_cache_ttl: int = int(os.getenv("SEMANTIC_CACHE_TTL", "3600"))
    faiss_cache_index_size: int = int(os.getenv("FAISS_CACHE_INDEX_SIZE", "10000"))


@dataclass
class RetrieverConfig:
    top_k: int = int(os.getenv("RETRIEVER_TOP_K", "20"))
    bm25_weight: float = float(os.getenv("BM25_WEIGHT", "0.3"))
    vector_weight: float = float(os.getenv("VECTOR_WEIGHT", "0.7"))
    min_vector_similarity: float = float(os.getenv("MIN_VECTOR_SIMILARITY", "0.0"))


@dataclass
class RerankerConfig:
    model_name: str = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    enabled: bool = os.getenv("RERANKER_ENABLED", "false").lower() == "true"
    top_n: int = int(os.getenv("RERANKER_TOP_N", "5"))


@dataclass
class OllamaConfig:
    base_url: str = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    timeout: int = int(os.getenv("OLLAMA_TIMEOUT", "5"))
    temperature: float = float(os.getenv("OLLAMA_TEMPERATURE", "0.3"))
    max_tokens: int = int(os.getenv("OLLAMA_MAX_TOKENS", "300"))


@dataclass
class QueryTransformConfig:
    hyde_enabled: bool = os.getenv("HYDE_ENABLED", "false").lower() == "true"
    rag_fusion_enabled: bool = os.getenv("RAG_FUSION_ENABLED", "false").lower() == "true"
    rag_fusion_queries: int = int(os.getenv("RAG_FUSION_QUERIES", "3"))
    step_back_enabled: bool = os.getenv("STEP_BACK_ENABLED", "false").lower() == "true"
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")


@dataclass
class IngestionConfig:
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/1")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/2")
    batch_size: int = int(os.getenv("INGESTION_BATCH_SIZE", "100"))


@dataclass
class ObservabilityConfig:
    enabled: bool = os.getenv("OBSERVABILITY_ENABLED", "false").lower() == "true"
    faithfulness_threshold: float = float(os.getenv("FAITHFULNESS_THRESHOLD", "0.7"))
    log_retrieval_metrics: bool = True


@dataclass
class MultiTenantConfig:
    enabled: bool = os.getenv("MULTI_TENANT_ENABLED", "false").lower() == "true"
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


config = RAGConfig()