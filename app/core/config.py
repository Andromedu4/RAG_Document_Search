from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "RAG for Document Search"
    app_env: str = "local"
    debug: bool = False

    database_url: str = "sqlite:///./ai_blog.db"
    secret_key: str = Field(default="dev-secret-change-me", min_length=8)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    ai_provider: str = "mock"
    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    openai_rag_model: str = "gpt-5.4-nano"
    openai_summary_model: str = "gpt-5.4-nano"
    openai_embedding_dimensions: int = 1536
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"

    chunk_max_chars: int = 1600
    chunk_overlap_chars: int = 220
    semantic_search_limit: int = 8
    rag_top_k: int = 6
    upload_dir: Path = Path("uploads")
    url_fetch_timeout_seconds: float = 10.0
    url_fetch_max_bytes: int = 1_500_000

    @field_validator("ai_provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        return value.lower().strip()

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def use_mock_provider(self) -> bool:
        return self.ai_provider == "mock"

    @property
    def rag_generation_model(self) -> str:
        if self.ai_provider == "groq":
            return self.groq_model
        return self.openai_rag_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
