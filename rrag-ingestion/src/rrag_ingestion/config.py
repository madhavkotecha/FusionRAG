from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "RRAG_"}

    # Server
    host: str = "0.0.0.0"
    port: int = 8001
    environment: str = "development"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://rrag:rrag_dev_password@localhost:5432/rrag"

    # Redis
    redis_url: str = "redis://localhost:6381/1"

    # Storage
    storage_dir: str = "./data/documents"
    configs_dir: str = "./configs"
    max_upload_size_mb: int = 100

    # LLM
    openai_api_key: str = ""
    default_llm_model: str = "gpt-4o-mini"
    default_embedding_model: str = "text-embedding-3-small"
    llm_provider: str = "openai"  # "openai", "ollama", or "vllm"
    openai_base_url: str = ""  # Custom base URL for OpenAI-compatible APIs
    ollama_base_url: str = "http://host.docker.internal:11434"
    vllm_base_url: str = "http://host.docker.internal:8000"
    vllm_api_key: str = "EMPTY"  # vLLM accepts any key when started without --api-key
    vllm_model: str = "Qwen/Qwen2.5-7B-Instruct"  # model name served by vLLM (--model)
    llm_request_timeout: int = 60  # per-call timeout (s) before fallback kicks in

    # Tiered model routing (ADR-0018): map a complexity tier to a concrete model.
    # For vLLM deployments, set these to the served model name(s).
    llm_model_fast: str = "gpt-4o-mini"  # simple queries / claim verification
    llm_model_capable: str = "gpt-4o"  # complex / multi-hop queries

    # Seamless fallback to OpenAI when a self-hosted vLLM server is unreachable.
    # ADR-0018: vLLM's OpenAI-compatible API makes this a drop-in fallback.
    llm_fallback_to_openai: bool = True
    openai_fallback_model: str = "gpt-4o-mini"  # OpenAI model used when falling back

    # Queue
    rq_queue_name: str = "ingestion"
    rq_job_timeout: int = 3600  # 1 hour

    # MinIO (S3-compatible object storage)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "rrag-documents"
    minio_use_ssl: bool = False

    # OpenSearch (hybrid vector + text search)
    opensearch_host: str = "localhost"
    opensearch_port: int = 9200
    opensearch_index_prefix: str = "rrag"
    opensearch_use_ssl: bool = False

    # Qdrant (dedicated vector search)
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""


settings = Settings()
