from __future__ import annotations

import logging
from typing import Callable, List, Optional, Tuple

from PIL import Image
from pydantic import BaseModel

from config import get_settings
from schemas import DocumentType

logger = logging.getLogger(__name__)

# LayoutLMv3 is a token-classification model, not generative — it tags
# each OCR'd word/box with a label. Label set is a placeholder until
# you fine-tune on the annotated set; refine per document_type.
LAYOUTLM_LABELS = ["O", "B-NAME", "I-NAME", "B-DATE", "I-DATE", "B-ORG", "I-ORG", "B-FIELD", "I-FIELD"]


class LayoutLMExtractionResult(BaseModel):
    document_type: DocumentType
    words: List[str]
    labels: List[str]
    parsed_json: dict
    confidence: float


class LayoutLMExtractionError(RuntimeError):
    """Raised when OCR or the model produce unusable output."""


def extract_with_layoutlm(
    image: Image.Image,
    document_type: DocumentType,
    ocr_fn: Optional[Callable[[Image.Image], Tuple[List[str], List[list]]]] = None,
    model_fn: Optional[Callable[[Image.Image, List[str], List[list]], List[str]]] = None,
) -> LayoutLMExtractionResult:
    ocr_fn = ocr_fn or _default_ocr
    model_fn = model_fn or _default_layoutlm_predict

    try:
        words, boxes = ocr_fn(image)
    except Exception as exc:  # noqa: BLE001
        raise LayoutLMExtractionError(f"OCR step failed: {exc}") from exc

    if not words:
        raise LayoutLMExtractionError("OCR returned no words — likely a blank or unreadable scan.")

    labels = model_fn(image, words, boxes)
    parsed = _labels_to_json(words, labels)

    return LayoutLMExtractionResult(
        document_type=document_type,
        words=words,
        labels=labels,
        parsed_json=parsed,
        confidence=_estimate_confidence(labels),
    )


def _labels_to_json(words: List[str], labels: List[str]) -> dict:
    result: dict = {}
    current_key, buffer = None, []
    for word, label in zip(words, labels):
        if label.startswith("B-"):
            if current_key:
                result[current_key] = " ".join(buffer)
            current_key, buffer = label[2:].lower(), [word]
        elif label.startswith("I-") and current_key:
            buffer.append(word)
        else:
            if current_key:
                result[current_key] = " ".join(buffer)
            current_key, buffer = None, []
    if current_key:
        result[current_key] = " ".join(buffer)
    return result


def _estimate_confidence(labels: List[str]) -> float:
    # proxy: fraction of tokens the model actually tagged (non-"O")
    if not labels:
        return 0.0
    tagged = sum(1 for l in labels if l != "O")
    return round(tagged / len(labels), 2)


# ---------------------------------------------------------------------------
# Default backends
# ---------------------------------------------------------------------------

_layoutlm_model = None
_layoutlm_processor = None


def _default_ocr(image: Image.Image) -> Tuple[List[str], List[list]]:
    # pytesseract gives word-level text + boxes; normalize boxes to 0-1000
    # scale (LayoutLMv3 convention) relative to image size.
    import pytesseract

    w, h = image.size
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

    words, boxes = [], []
    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue
        x, y, bw, bh = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        box = [
            int(1000 * x / w), int(1000 * y / h),
            int(1000 * (x + bw) / w), int(1000 * (y + bh) / h),
        ]
        words.append(word)
        boxes.append(box)
    return words, boxes


def _get_processor(settings):
    global _layoutlm_processor
    if _layoutlm_processor is None:
        from transformers import LayoutLMv3Processor
        _layoutlm_processor = LayoutLMv3Processor.from_pretrained(
            settings.layoutlm_model_name, apply_ocr=False
        )
    return _layoutlm_processor


def _get_model(settings):
    global _layoutlm_model
    if _layoutlm_model is None:
        from transformers import LayoutLMv3ForTokenClassification
        _layoutlm_model = LayoutLMv3ForTokenClassification.from_pretrained(
            settings.layoutlm_model_name, num_labels=len(LAYOUTLM_LABELS)
        )
        if settings.device == "cuda":
            _layoutlm_model = _layoutlm_model.to("cuda")
    return _layoutlm_model


def _default_layoutlm_predict(image: Image.Image, words: List[str], boxes: List[list]) -> List[str]:
    import torch

    settings = get_settings()
    processor = _get_processor(settings)
    model = _get_model(settings)

    encoding = processor(image, words, boxes=boxes, return_tensors="pt", truncation=True)
    if settings.device == "cuda":
        encoding = {k: v.to("cuda") for k, v in encoding.items()}

    with torch.no_grad():
        outputs = model(**encoding)

    predictions = outputs.logits.argmax(-1).squeeze().tolist()
    predictions = predictions if isinstance(predictions, list) else [predictions]
    return [LAYOUTLM_LABELS[p % len(LAYOUTLM_LABELS)] for p in predictions[: len(words)]]
