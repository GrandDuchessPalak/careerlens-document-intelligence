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
