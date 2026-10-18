from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "mysql+pymysql://rag:CHANGE_ME@localhost:3306/enterprise_support_rag?charset=utf8mb4"
    jwt_secret: SecretStr = SecretStr("")
    token_minutes: int = Field(default=60, ge=1, le=1440)
    redis_url: str = "redis://localhost:6379/6"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "ragadmin"
    minio_secret_key: SecretStr = SecretStr("")
    minio_secure: bool = False
    minio_bucket: str = "enterprise-support-rag-documents"
    milvus_uri: str = "http://localhost:19530"
    milvus_collection: str = "enterprise_support_rag_v001"
    embedding_url: str = "http://localhost:8001"
    reranker_url: str = "http://localhost:8002"
    model_service_key: SecretStr = SecretStr("")
    embedding_model: str = "BAAI/bge-m3"
    embedding_revision: str = "main"
    embedding_version: str = "bge-m3-initial"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_revision: str = "main"
    model_device: str = "cpu"
    model_use_fp16: bool = False
    embedding_max_length: int = Field(default=1024, ge=128, le=8192)
    chunk_max_tokens: int = Field(default=600, ge=64, le=7000)
    chunk_overlap_tokens: int = Field(default=60, ge=0)
    sentence_min_tokens: int = Field(default=48, ge=1, le=600)
    sentence_max_tokens: int = Field(default=200, ge=32, le=600)
    window_neighbors: int = Field(default=2, ge=0, le=5)
    window_max_tokens: int = Field(default=800, ge=64, le=1200)
    upload_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    dense_top_k: int = Field(default=50, ge=1, le=200)
    sparse_top_k: int = Field(default=50, ge=1, le=200)
    fusion_top_k: int = Field(default=30, ge=1, le=200)
    context_top_k: int = Field(default=8, ge=1, le=20)
    context_char_budget: int = Field(default=16000, ge=1000, le=40000)
    llm_base_url: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    llm_max_tokens: int = Field(default=1800, ge=256, le=8192)
    query_planner_enabled: bool = True
    query_planner_timeout_seconds: float = Field(default=20, gt=0)
    llm_timeout_seconds: float = Field(default=90, gt=0)
    external_timeout_seconds: float = Field(default=60, gt=0)

    @model_validator(mode="after")
    def validate_lengths(self):
        if self.sentence_min_tokens > self.sentence_max_tokens:
            raise ValueError("sentence_min_tokens must not exceed sentence_max_tokens")
        if self.sentence_max_tokens + 128 > self.embedding_max_length:
            raise ValueError("sentence_max_tokens must leave 128 embedding tokens")
        if self.window_max_tokens < self.sentence_max_tokens:
            raise ValueError("window must fit at least one sentence unit")
        if self.chunk_overlap_tokens >= self.chunk_max_tokens:
            raise ValueError("chunk overlap must be smaller than chunk size")
        # Reserve tokens for metadata and special tokens.
        if self.chunk_max_tokens + 128 > self.embedding_max_length:
            raise ValueError("embedding_max_length must allow 128 metadata tokens")
        return self

    def validate_runtime(self):
        secret = self.jwt_secret.get_secret_value()
        if len(secret) < 32 or secret.startswith("CHANGE_ME"):
            raise ValueError("Set JWT_SECRET to a random value of at least 32 characters")


@lru_cache
def get_settings() -> Settings:
    return Settings()
