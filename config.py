"""
config.py

Central configuration for CareerLens: model names/paths, storage paths,
the confidence threshold used to decide when to fall back to prompted
VLM extraction, and vector DB / API settings.

Secrets (API keys, tokens) live in `.env` and are never hardcoded here.
Everything else (paths, thresholds, model names) has a sensible default
so the project runs out of the box, but can be overridden via `.env`
or real environment variables without touching this file.

Usage:
    from config import get_settings
    settings = get_settings()
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- App -----------------------------------------------------------
    app_name: str = "CareerLens"
    environment: Literal["development", "production"] = "development"

    # -- Storage paths ---------------------------------------------------
    # Runtime data (uploaded documents, extracted JSON, embeddings) lives
    # under storage_root. Subpaths are derived, not set independently, so
    # there's one place to change if the layout ever moves.
    storage_root: Path = Path("storage")

    @property
    def documents_dir(self) -> Path:
        return self.storage_root / "documents"

    @property
    def metadata_dir(self) -> Path:
        return self.storage_root / "metadata"

    @property
    def json_dir(self) -> Path:
        return self.storage_root / "json"

    @property
    def embeddings_dir(self) -> Path:
        return self.storage_root / "embeddings"

    # -- Models ----------------------------------------------------------
    donut_model_name: str = "naver-clova-ix/donut-base"
    layoutlm_model_name: str = "microsoft/layoutlmv3-base"
    hf_cache_dir: Path = Path(".hf_cache")
    device: Literal["cpu", "cuda", "auto"] = "auto"

    # Prompted-VLM fallback (used when no labeled data exists for a
    # field/document type, or when a fine-tuned model's confidence is
    # too low — see fallback_confidence_threshold below).
    vlm_provider: Literal["openai", "qwen", "claude"] = "openai"
    vlm_model_name: str = "gpt-4o"

    # Below this confidence, the extraction pipeline should re-attempt
    # the field via prompted VLM extraction instead of trusting the
    # fine-tuned model's output.
    fallback_confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)

    # -- Vector DB / RAG ---------------------------------------------------
    vector_db_path: Path = Path("storage/embeddings/chroma")
    vector_db_collection: str = "careerlens_documents"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    # -- API ---------------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # -- Logging -------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # -- Secrets (set these in .env, never here) --------------------------
    hf_token: SecretStr | None = None
    vlm_api_key: SecretStr | None = None

    @model_validator(mode="after")
    def _ensure_storage_dirs_exist(self) -> "Settings":
        for path in (
            self.storage_root,
            self.documents_dir,
            self.metadata_dir,
            self.json_dir,
            self.embeddings_dir,
            self.hf_cache_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        return self


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings singleton. Import and call this everywhere config is
    needed instead of instantiating Settings() directly, so the whole
    app shares one instance and .env is only read once.
    """
    return Settings()