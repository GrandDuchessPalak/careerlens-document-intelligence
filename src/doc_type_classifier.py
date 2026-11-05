"""Zero-shot document-type classifier (CLIP) for the 3 v1 classes.

Kept deliberately simple. Upgrade path: fine-tune on RVL-CDIP's resume class + a few of your own
labelled transcripts/certificates, or replace with a prompted VLM call.
"""
from typing import Tuple

import config

PROMPTS = {
    "resume": "a scan of a resume or CV with sections for skills, education and experience",
    "transcript": "an academic transcript or marksheet with a table of subjects and grades",
    "certificate": "a certificate of completion or achievement with a title, signature or seal",
}

_cache = {}


def _load():
    if "m" not in _cache:
        import torch
        from transformers import CLIPModel, CLIPProcessor
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        _cache["m"] = (CLIPProcessor.from_pretrained(config.CLASSIFIER_MODEL),
                       CLIPModel.from_pretrained(config.CLASSIFIER_MODEL).to(dev).eval(), dev)
    return _cache["m"]


def classify(image) -> Tuple[str, float]:
    """Return (doc_type, probability) for a page image."""
    import torch
    proc, model, dev = _load()
    labels = list(PROMPTS)
    inputs = proc(text=list(PROMPTS.values()), images=image.convert("RGB"),
                  return_tensors="pt", padding=True).to(dev)
    with torch.no_grad():
        probs = model(**inputs).logits_per_image.softmax(dim=-1)[0]
    i = int(probs.argmax())
    return labels[i], float(probs[i])
