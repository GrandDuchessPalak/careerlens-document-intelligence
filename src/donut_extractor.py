"""Donut (OCR-free) baseline. The DocVQA checkpoint is queried once per scalar field using the
questions in schemas.FIELD_QUESTIONS. Confidence = mean token probability of the generated answer."""
import re

import config
from .schemas import FIELD_QUESTIONS, SCALAR_FIELDS
from .utils import log, to_float


class DonutExtractor:
    name = "donut"

    def __init__(self):
        self._proc = self._model = None
        self.device = None

    def _load(self):
        if self._model is None:
            import torch
            from transformers import DonutProcessor, VisionEncoderDecoderModel
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self._proc = DonutProcessor.from_pretrained(config.DONUT_MODEL)
            self._model = VisionEncoderDecoderModel.from_pretrained(config.DONUT_MODEL).to(self.device).eval()

    def ask(self, image, question: str, max_length: int = 128):
        """Return (answer_text, confidence in [0,1])."""
        import torch
        self._load()
        tok = self._proc.tokenizer
        prompt = f"<s_docvqa><s_question>{question}</s_question><s_answer>"
        pv = self._proc(image.convert("RGB"), return_tensors="pt").pixel_values.to(self.device)
        ids = tok(prompt, add_special_tokens=False, return_tensors="pt").input_ids.to(self.device)
        with torch.no_grad():
            out = self._model.generate(
                pv, decoder_input_ids=ids, max_length=max_length, early_stopping=True,
                pad_token_id=tok.pad_token_id, eos_token_id=tok.eos_token_id, use_cache=True,
                num_beams=1, bad_words_ids=[[tok.unk_token_id]],
                return_dict_in_generate=True, output_scores=True)
        seq = self._proc.batch_decode(out.sequences)[0]
        seq = seq.replace(tok.eos_token, "").replace(tok.pad_token, "")
        seq = re.sub(r"<.*?>", "", seq, count=1).strip()
        parsed = self._proc.token2json(seq)
        answer = str(parsed.get("answer", "")).strip() if isinstance(parsed, dict) else ""
        try:
            scores = self._model.compute_transition_scores(out.sequences, out.scores, normalize_logits=True)
            conf = float(torch.exp(scores[0].mean()))
        except Exception as e:
            log.warning("could not compute Donut confidence: %s", e)
            conf = 0.0
        return answer, max(0.0, min(1.0, conf))

    def extract(self, images, doc_type: str) -> dict:
        fields = {}
        for name in SCALAR_FIELDS[doc_type]:
            ans, conf = self.ask(images[0], FIELD_QUESTIONS[name])
            value = (to_float(ans) if name == "cgpa" else ans) or None
            fields[name] = {"value": value, "confidence": conf if value is not None else 0.0}
        return fields
