from __future__ import annotations

import logging
from typing import List

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ATSResult(BaseModel):
    score: float
    matched_keywords: List[str]
    missing_keywords: List[str]
    explanation: str


class ATSError(RuntimeError):
    pass


def score_resume(resume_json: dict, job_description: str) -> ATSResult:
    """
    Placeholder v2 scoring — naive keyword overlap. Replace with an
    embedding-similarity or LLM-scored version once v1 extraction is stable.
    """
    resume_text = " ".join(str(v) for v in resume_json.values()).lower()
    jd_words = {w.strip(".,()") for w in job_description.lower().split() if len(w) > 3}

    matched = [w for w in jd_words if w in resume_text]
    missing = [w for w in jd_words if w not in resume_text]

    score = round(len(matched) / len(jd_words), 3) if jd_words else 0.0

    return ATSResult(
        score=score,
        matched_keywords=sorted(matched),
        missing_keywords=sorted(missing),
        explanation=f"{len(matched)}/{len(jd_words)} JD keywords found in resume.",
    )