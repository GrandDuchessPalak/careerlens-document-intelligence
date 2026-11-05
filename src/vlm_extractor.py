"""Schema-prompted extraction with a general VLM (zero-shot, no training). Fills ALL fields,
including arrays and signature/stamp flags. Confidences are the model's own (verbalised) estimates:
useful for ranking, NOT calibrated probabilities."""
import json

from pydantic import ValidationError

import config
from .schemas import FIELDS_MODEL, schema_example
from .utils import extract_json, llm_complete, log

SYSTEM = ("You extract structured data from document images. Respond with a single JSON object only: "
          "no preamble, no markdown, no commentary.")

PROMPT = """This document is a {doc_type}. Extract its contents into JSON with EXACTLY this structure:
{template}

Rules:
- Scalar fields are {{"value": ..., "confidence": ...}}; array entries carry one "confidence" for the whole entry.
- confidence is your own estimate between 0.0 and 1.0 of how sure you are the value is correct.
- If a field is not present, use null for its value (or an empty list) and confidence 0.0.
- Copy text exactly as printed. Do not invent values.
- For certificates, signature_detected / stamp_detected are true or false depending on what is visible.
- For transcripts, cgpa is a number.
"""


class VLMExtractor:
    name = "prompted_vlm"

    def extract(self, images, doc_type: str) -> dict:
        prompt = PROMPT.format(doc_type=doc_type, template=json.dumps(schema_example(doc_type), indent=1))
        cls = FIELDS_MODEL[doc_type]
        last_err = None
        for attempt in range(2):
            p = prompt if attempt == 0 else (
                prompt + f"\nYour previous answer was invalid ({last_err}). Return valid JSON only.")
            try:
                data = extract_json(llm_complete(p, system=SYSTEM, images=images[:config.MAX_PAGES]))
                data = data.get("fields", data)            # tolerate an extra wrapper
                return cls.model_validate(data).model_dump()
            except (ValueError, ValidationError) as e:
                last_err = str(e)[:300]
                log.warning("VLM output invalid (attempt %d): %s", attempt + 1, last_err)
        raise RuntimeError(f"VLM did not return valid JSON: {last_err}")
