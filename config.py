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
