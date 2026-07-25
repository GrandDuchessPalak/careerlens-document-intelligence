from _future_ import annotations

import json
import logging
from typing import Callable, Optional, Tuple

from PIL import Image
from pydantic import BaseModel, Field, ValidationError

from config import get_settings
from schemas import DocumentType

logger = logging.getLogger(_name_)

# RVL-CDIP's own label from the pretrained checkpoint. Only "resume" is
# useful to us — no other RVL-CDIP class maps cleanly onto certificate
# or transcript.
RVLCDIP_RESUME_LABEL = "resume"
RVLCDIP_CONFIDENCE_THRESHOLD = 0.75  # trust the cheap signal above this; otherwise fall back to VLM

VLM_CLASSIFICATION_PROMPT = """You are a document classifier. Look at the provided
document image and decide which ONE of the following three categories it belongs to:

- "resume": a CV/resume listing a person's skills, education, and work experience
- "transcript": a university/college transcript or marksheet showing grades/CGPA
- "certificate": a certificate of completion, achievement, or internship

Respond with ONLY a JSON object, no other text, in this exact form:
{"document_type": "resume" | "transcript" | "certificate", "confidence": <float 0.0-1.0>}
"""


class ClassificationResult(BaseModel):
    document_type: DocumentType
    confidence: float = Field(ge=0.0, le=1.0)
    source: str  # "rvlcdip" or "vlm" — which signal actually produced this result


class ClassificationError(RuntimeError):
    """Raised when neither signal can produce a valid classification."""


def classify_document(
    image: Image.Image,
    rvlcdip_fn: Optional[Callable[[Image.Image], Tuple[str, float]]] = None,
    vlm_fn: Optional[Callable[[Image.Image, str], str]] = None,
) -> ClassificationResult:
    """
    Classify a single document image into resume/transcript/certificate.

    rvlcdip_fn and vlm_fn are injection points for the real model
    calls (_default_rvlcdip_classify / _default_vlm_classify below).
    Pass overrides in tests, or to swap either backend later, without
    touching this orchestration logic.
    """
    rvlcdip_fn = rvlcdip_fn or _default_rvlcdip_classify
    vlm_fn = vlm_fn or _default_vlm_classify

    try:
        label, confidence = rvlcdip_fn(image)
        if label == RVLCDIP_RESUME_LABEL and confidence >= RVLCDIP_CONFIDENCE_THRESHOLD:
            return ClassificationResult(document_type="resume", confidence=confidence, source="rvlcdip")
    except Exception as exc:  # noqa: BLE001 — a failed cheap signal should never block classification
        logger.warning("RVL-CDIP pass failed, falling back to VLM: %s", exc)

    raw_response = vlm_fn(image, VLM_CLASSIFICATION_PROMPT)
    return _parse_vlm_response(raw_response)


def _parse_vlm_response(raw_response: str) -> ClassificationResult:
    try:
        parsed = json.loads(raw_response.strip())
        return ClassificationResult(
            document_type=parsed["document_type"],
            confidence=parsed["confidence"],
            source="vlm",
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
        raise ClassificationError(
            f"VLM classifier returned an unusable response: {raw_response!r}"
        ) from exc


# ---------------------------------------------------------------------------
# Default backends — the real model calls. Swap these (or pass overrides to
# classify_document) if you change providers/models later.
# ---------------------------------------------------------------------------

_rvlcdip_pipeline = None  # lazy-loaded, module-level cache — importing this file shouldn't trigger a model download


def _default_rvlcdip_classify(image: Image.Image) -> Tuple[str, float]:
    """
    Runs a pretrained RVL-CDIP document classifier
    ("microsoft/dit-base-finetuned-rvlcdip") and returns its top label
    and confidence.
    """
    global _rvlcdip_pipeline

    if _rvlcdip_pipeline is None:
        from transformers import pipeline  # imported lazily so module import stays light

        settings = get_settings()
        _rvlcdip_pipeline = pipeline(
            "image-classification",
            model="microsoft/dit-base-finetuned-rvlcdip",
            device=0 if settings.device == "cuda" else -1,
        )

    predictions = _rvlcdip_pipeline(image)
    top = predictions[0]
    return top["label"].lower(), float(top["score"])


def _default_vlm_classify(image: Image.Image, prompt: str) -> str:
    """Calls the configured VLM provider (see config.py) with the classification prompt."""
    settings = get_settings()

    if settings.vlm_provider == "openai":
        import base64
        from io import BytesIO

        from openai import OpenAI

        client = OpenAI(
            api_key=settings.vlm_api_key.get_secret_value() if settings.vlm_api_key else None
        )

        buffer = BytesIO()
        image.save(buffer, format="PNG")
        b64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

        response = client.chat.completions.create(
            model=settings.vlm_model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}},
                    ],
                }
            ],
            max_tokens=100,
        )
        return response.choices[0].message.content

    raise NotImplementedError(
        f"VLM provider '{settings.vlm_provider}' isn't wired up yet — "
        "add a branch here following the same pattern as the openai branch."
    )