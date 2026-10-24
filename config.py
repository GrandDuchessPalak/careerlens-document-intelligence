<<<<<<< HEAD
"""Central configuration. Secrets live in .env (see .env.example)."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

# ---- storage -------------------------------------------------------------
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", ROOT / "storage"))
DOCUMENTS_DIR = STORAGE_DIR / "documents"
METADATA_DIR = STORAGE_DIR / "metadata"
JSON_DIR = STORAGE_DIR / "json"
EMBEDDINGS_DIR = STORAGE_DIR / "embeddings"
ANNOTATED_DIR = ROOT / "data" / "annotated"
ALLOWED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}

# ---- models (lazy-loaded on first use) -------------------------------------
# Donut: DocVQA checkpoint, queried field-by-field with schema questions.
DONUT_MODEL = os.getenv("DONUT_MODEL", "naver-clova-ix/donut-base-finetuned-docvqa")
# OCR-dependent baseline: any HF "document-question-answering" checkpoint.
# Default is LayoutLM (v1). Swap in a LayoutLMv3 DocVQA / fine-tuned checkpoint here.
LAYOUTLM_MODEL = os.getenv("LAYOUTLM_MODEL", "impira/layoutlm-document-qa")
CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL", "openai/clip-vit-base-patch32")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# ---- LLM / VLM ----------------------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")      # anthropic | groq
VLM_MODEL = os.getenv("VLM_MODEL", "claude-sonnet-5-5")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")          # text (RAG)
# Vision model for extraction. Groq rotates models: check https://console.groq.com/docs/models for a
# current vision-capable ID and override here if this one has been retired.
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.6-27b")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ---- pipeline knobs --------------------------------------------------------------
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))  # UI flags fields below this
PDF_DPI = 200
MAX_IMAGE_SIDE = 2200
MAX_PAGES = 3
CHUNK_CHARS = 800
TOP_K = 5
=======
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
>>>>>>> 22298f89189fd0a2a37213efc84616474a0cc990
