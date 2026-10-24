<<<<<<< HEAD
"""V2 (optional): explainable, rule-based ATS check on an extracted resume. Heuristics follow common
ATS guidance (contact info, skills keywords, quantified achievements, action verbs); always returns reasons.
JD matching, career recommendations and interview questions are not implemented in v1."""
import re

ACTION_VERBS = {"built", "developed", "designed", "implemented", "led", "created", "improved", "optimized",
                "deployed", "automated", "reduced", "increased", "trained", "analyzed", "engineered"}


def ats_score(resume: dict) -> dict:
    f = resume["fields"]
    score, reasons = 100, []

    for key in ("name", "email", "phone"):
        if not f[key]["value"]:
            score -= 8
            reasons.append(f"missing {key}")
    if len(f["skills"]["value"] or []) < 5:
        score -= 15
        reasons.append("fewer than 5 skills listed")
    if not f["education"]:
        score -= 10
        reasons.append("no education section detected")
    if not f["experience"] and not f["projects"]:
        score -= 15
        reasons.append("no experience or projects detected")

    text = " ".join((p.get("description") or "") for p in f["projects"])
    if text and not re.search(r"\d+\s?(%|x|\+|k\b|ms\b)|\$\s?\d", text, re.I):
        score -= 15
        reasons.append("missing quantified achievements in project descriptions")
    if text and not (set(re.findall(r"[a-z]+", text.lower())) & ACTION_VERBS):
        score -= 10
        reasons.append("no action verbs in project descriptions")

    return {"ats_score": max(score, 0), "reasons": reasons or ["no issues found by the v1 rules"]}
=======
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
>>>>>>> 22298f89189fd0a2a37213efc84616474a0cc990
