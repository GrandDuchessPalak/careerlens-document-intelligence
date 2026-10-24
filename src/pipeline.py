"""Orchestration: preprocess -> classify -> extract -> store -> index. Deliberate addition to the frozen
structure so the API and the benchmark share one extractor registry."""
from datetime import datetime, timezone
from typing import Optional

from . import pdf_to_image
from .schemas import ModelName, build_doc
from .storage import Storage
from .utils import log, ocr_text

_extractors = {}


def get_extractor(model: str):
    model = ModelName(model).value
    if model not in _extractors:
        if model == "donut":
            from .donut_extractor import DonutExtractor as C
        elif model == "layoutlmv3":
            from .layoutlm_extractor import LayoutLMExtractor as C
        else:
            from .vlm_extractor import VLMExtractor as C
        _extractors[model] = C()
    return _extractors[model]


def process(storage: Storage, doc_id: str, version: int, model: str = "prompted_vlm",
            doc_type: Optional[str] = None, index: bool = True):
    """Run the full pipeline for one stored document version and return the validated ExtractionDoc."""
    images = pdf_to_image.prepare(storage.document_path(doc_id, version))
    meta = storage.load_metadata(doc_id, version)

    if doc_type is None:
        doc_type = meta.document_type.value if meta.document_type else None
    if doc_type is None:
        from .doc_type_classifier import classify
        doc_type, conf = classify(images[0])
        meta.classifier_confidence = conf

    fields = get_extractor(model).extract(images, doc_type)
    doc = build_doc(doc_id, version, doc_type, model, fields)
    storage.save_json(doc)

    meta.document_type, meta.extraction_model = doc_type, ModelName(model)
    meta.extracted_at = datetime.now(timezone.utc)
    storage.save_metadata(meta)

    if index:
        try:
            from .vector_store import VectorStore
            raw = "\n".join(ocr_text(im) for im in images)
            VectorStore().index_document(doc.model_dump(mode="json"), raw)
        except Exception as e:      # indexing must not lose a finished extraction
            log.warning("indexing failed: %s", e)
    return doc
