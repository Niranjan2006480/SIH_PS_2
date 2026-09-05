"""
UdyamAI — Application Configuration
Reads all settings from environment variables / .env file.
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────────────────────
    app_env: Literal["development", "production", "test"] = "development"
    app_name: str = "UdyamAI"
    secret_key: str = "change-me-in-production"

    # ── Database (Supabase PostgreSQL) ────────────────────────────────────────
    database_url: str
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "reports"

    # ── Google Gemini ─────────────────────────────────────────────────────────
    google_gemini_api_key: str
    gemini_model: str = "gemini-2.0-flash"
    gemini_temperature: float = 0.3
    gemini_max_output_tokens: int = 8192

    # ── Qdrant ────────────────────────────────────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_grpc_port: int = 6334
    qdrant_collection_name: str = "udyamai_knowledge"

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_report_ttl_seconds: int = 3600       # 1 hour
    redis_location_ttl_seconds: int = 86400    # 24 hours

    # ── Ollama (bge-m3 embeddings) ────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "bge-m3"

    # ── FastAPI ───────────────────────────────────────────────────────────────
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_reload: bool = True
    backend_log_level: str = "info"
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: str) -> str:
        return v

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def async_database_url(self) -> str:
        """Convert psycopg2 URL to asyncpg format."""
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
