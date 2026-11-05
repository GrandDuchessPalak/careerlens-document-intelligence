"""OCR-dependent baseline: OCR (Tesseract) -> words + boxes -> LayoutLM-family document QA.

Two-stage by design: the HF `document-question-answering` pipeline runs Tesseract internally, so
Tesseract must be installed. Default checkpoint is LayoutLM (v1); set LAYOUTLM_MODEL to a LayoutLMv3
DocVQA / your own fine-tuned checkpoint to benchmark v3. Confidence = the pipeline's answer score."""
import config
from .schemas import FIELD_QUESTIONS, SCALAR_FIELDS
from .utils import to_float


class LayoutLMExtractor:
    name = "layoutlmv3"   # enum slot for the OCR-dependent LayoutLM family

    def __init__(self):
        self._pipe = None

    def _load(self):
        if self._pipe is None:
            import torch
            from transformers import pipeline
            self._pipe = pipeline("document-question-answering", model=config.LAYOUTLM_MODEL,
                                  device=0 if torch.cuda.is_available() else -1)

    def ask(self, image, question: str):
        self._load()
        res = self._pipe(image=image.convert("RGB"), question=question, top_k=1)
        if isinstance(res, list):
            res = res[0] if res else {}
        return str(res.get("answer", "")).strip(), float(res.get("score", 0.0))

    def extract(self, images, doc_type: str) -> dict:
        fields = {}
        for name in SCALAR_FIELDS[doc_type]:
            ans, conf = self.ask(images[0], FIELD_QUESTIONS[name])
            value = (to_float(ans) if name == "cgpa" else ans) or None
            fields[name] = {"value": value, "confidence": max(0.0, min(1.0, conf)) if value is not None else 0.0}
        return fields
