from __future__ import annotations

import json
import logging
from typing import Callable, Optional

from PIL import Image
from pydantic import BaseModel, ValidationError

from config import get_settings
from schemas import DocumentType

logger = logging.getLogger(__name__)

# Donut needs a task-specific prompt token per doc type; these are the
# ones the base checkpoint was pretrained with for document parsing.
DONUT_TASK_PROMPTS = {
    "resume": "<s_cord-v2>",
    "transcript": "<s_cord-v2>",
    "certificate": "<s_cord-v2>",
}


class DonutExtractionResult(BaseModel):
    document_type: DocumentType
    raw_output: str
    parsed_json: dict
    confidence: float


class DonutExtractionError(RuntimeError):
    """Raised when Donut produces output that can't be parsed into JSON."""


def extract_with_donut(
    image: Image.Image,
    document_type: DocumentType,
    model_fn: Optional[Callable[[Image.Image, str], str]] = None,
) -> DonutExtractionResult:
    model_fn = model_fn or _default_donut_generate
    prompt = DONUT_TASK_PROMPTS.get(document_type, "<s_cord-v2>")

    raw_output = model_fn(image, prompt)
    parsed = _parse_donut_output(raw_output)

    return DonutExtractionResult(
        document_type=document_type,
        raw_output=raw_output,
        parsed_json=parsed,
        confidence=_estimate_confidence(parsed),
    )


def _parse_donut_output(raw_output: str) -> dict:
    # Donut emits XML-like tags, not JSON — token2json is the standard
    # HF utility for this checkpoint family.
    try:
        from transformers.models.donut.processing_donut import DonutProcessor

        settings = get_settings()
        processor = _get_processor(settings)
        return processor.token2json(raw_output)
    except Exception as exc:  # noqa: BLE001
        raise DonutExtractionError(f"Could not parse Donut output: {raw_output!r}") from exc


def _estimate_confidence(parsed: dict) -> float:
    # Donut gives no native per-field confidence. Use non-empty-field
    # ratio as a cheap proxy until you replace this with something real
    # (e.g. token-level logprob averaging).
    if not parsed:
        return 0.0
    filled = sum(1 for v in parsed.values() if v)
    return round(filled / len(parsed), 2)


# ---------------------------------------------------------------------------
# Default backend
# ---------------------------------------------------------------------------

_donut_model = None
_donut_processor = None


def _get_processor(settings):
    global _donut_processor
    if _donut_processor is None:
        from transformers import DonutProcessor
        _donut_processor = DonutProcessor.from_pretrained(settings.donut_model_name)
    return _donut_processor


def _get_model(settings):
    global _donut_model
    if _donut_model is None:
        from transformers import VisionEncoderDecoderModel
        _donut_model = VisionEncoderDecoderModel.from_pretrained(settings.donut_model_name)
        if settings.device == "cuda":
            _donut_model = _donut_model.to("cuda")
    return _donut_model


def _default_donut_generate(image: Image.Image, prompt: str) -> str:
    import torch

    settings = get_settings()
    processor = _get_processor(settings)
    model = _get_model(settings)

    pixel_values = processor(image, return_tensors="pt").pixel_values
    decoder_input_ids = processor.tokenizer(prompt, add_special_tokens=False, return_tensors="pt").input_ids

    if settings.device == "cuda":
        pixel_values = pixel_values.to("cuda")
        decoder_input_ids = decoder_input_ids.to("cuda")

    with torch.no_grad():
        outputs = model.generate(
            pixel_values,
            decoder_input_ids=decoder_input_ids,
            max_length=model.decoder.config.max_position_embeddings,
            pad_token_id=processor.tokenizer.pad_token_id,
            eos_token_id=processor.tokenizer.eos_token_id,
        )

    return processor.batch_decode(outputs)[0]