"""Validated application settings sourced from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration; secrets are never exposed through the API."""

    app_name: str = "Multi-Document RAG Research Assistant"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/research_assistant.db"
    upload_dir: Path = Path("./data/uploads")
    max_upload_mb: int = 100
    llm_provider: str = "gemini"
    llm_model: str = "gemini-2.5-flash"
    google_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    embedding_provider: str = "gemini"
    embedding_model: str = "gemini-embedding-001"
    retrieval_top_k: int = 10
    rerank_candidate_k: int = 20
    qdrant_path: Path = Path("./data/qdrant")
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    reranker: str = "none"
    cohere_api_key: str | None = None
    cohere_rerank_model: str = "rerank-v5.0-fast"
    local_reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings for this process."""

    return Settings()
