<<<<<<< HEAD
"""Field-level evaluation: accuracy, exact match, precision/recall/F1, list F1 for arrays."""
import re
from collections import defaultdict
from typing import Dict, List

# key used to compare array entries (set-based F1)
ARRAY_KEYS = {"education": "institution", "experience": "company", "projects": "title",
              "semester_marks": "subject"}


def norm(field: str, v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, (int, float)):
        return f"{float(v):.2f}"
    s = str(v).casefold().strip()
    if field == "phone":
        return re.sub(r"\D", "", s)
    s = re.sub(r"[^\w@.+\- ]", " ", s)
    return re.sub(r"\s+", " ", s).strip(" .")


def values_match(field: str, pred, gold) -> bool:
    if isinstance(gold, (int, float)) and not isinstance(gold, bool):
        try:
            return abs(float(pred) - float(gold)) < 0.01
        except (TypeError, ValueError):
            return False
    return norm(field, pred) == norm(field, gold)


def set_f1(pred: List[str], gold: List[str]) -> float:
    p, g = {norm("", x) for x in pred if x}, {norm("", x) for x in gold if x}
    if not p and not g:
        return 1.0
    tp = len(p & g)
    if not tp:
        return 0.0
    prec, rec = tp / len(p), tp / len(g)
    return 2 * prec * rec / (prec + rec)


def score_document(pred: Dict, gold: Dict, scalar_fields: List[str]) -> Dict:
    """pred/gold are plain {field: value} dicts. Returns per-field results plus list F1 for arrays."""
    fields = {}
    for f in scalar_fields:
        g, p = gold.get(f), pred.get(f)
        fields[f] = {"gold": g, "pred": p, "gold_present": g not in (None, ""),
                     "pred_present": p not in (None, ""),
                     "correct": values_match(f, p, g) if g not in (None, "") else p in (None, "")}
    lists = {}
    if "skills" in gold or "skills" in pred:
        lists["skills"] = set_f1(pred.get("skills") or [], gold.get("skills") or [])
    for arr, key in ARRAY_KEYS.items():
        if arr in gold:
            lists[arr] = set_f1([e.get(key) for e in pred.get(arr) or []],
                                [e.get(key) for e in gold.get(arr) or []])
    return {"fields": fields, "lists": lists}


def aggregate(doc_scores: List[Dict]) -> Dict:
    per_field = defaultdict(lambda: {"n": 0, "correct": 0})
    tp = fp = fn = 0
    exact = 0
    for s in doc_scores:
        all_ok = True
        for f, r in s["fields"].items():
            if r["gold_present"]:
                per_field[f]["n"] += 1
                per_field[f]["correct"] += int(r["correct"])
            ok_pred = r["pred_present"] and r["correct"] and r["gold_present"]
            tp += int(ok_pred)
            fp += int(r["pred_present"] and not ok_pred)
            fn += int(r["gold_present"] and not ok_pred)
            all_ok &= r["correct"]
        exact += int(all_ok)
    n_fields = sum(v["n"] for v in per_field.values())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    list_f1 = defaultdict(list)
    for s in doc_scores:
        for k, v in s["lists"].items():
            list_f1[k].append(v)
    return {
        "n_docs": len(doc_scores),
        "extraction_accuracy": sum(v["correct"] for v in per_field.values()) / n_fields if n_fields else 0.0,
        "exact_match": exact / len(doc_scores) if doc_scores else 0.0,
        "precision": prec, "recall": rec,
        "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
        "field_accuracy": {f: v["correct"] / v["n"] for f, v in per_field.items()},
        "list_f1": {k: sum(v) / len(v) for k, v in list_f1.items()},
    }
=======
from __future__ import annotations

import time
from typing import Callable, List

from pydantic import BaseModel


class DocMetrics(BaseModel):
    doc_id: str
    exact_match: bool
    field_accuracy: float
    latency_sec: float


class BenchmarkSummary(BaseModel):
    model_name: str
    avg_field_accuracy: float
    exact_match_rate: float
    avg_latency_sec: float
    n_docs: int


def score_document(predicted: dict, ground_truth: dict) -> tuple[bool, float]:
    """Compares predicted JSON vs. hand-labeled ground truth for one doc."""
    if not ground_truth:
        return False, 0.0

    keys = set(ground_truth.keys())
    correct = sum(
        1 for k in keys
        if _normalize(predicted.get(k)) == _normalize(ground_truth.get(k))
    )
    field_accuracy = correct / len(keys) if keys else 0.0
    exact_match = field_accuracy == 1.0
    return exact_match, round(field_accuracy, 3)


def time_extraction(extract_fn: Callable[[], dict]) -> tuple[dict, float]:
    start = time.perf_counter()
    result = extract_fn()
    elapsed = time.perf_counter() - start
    return result, round(elapsed, 3)


def summarize(results: List[DocMetrics], model_name: str) -> BenchmarkSummary:
    n = len(results)
    if n == 0:
        raise ValueError("No results to summarize")
    return BenchmarkSummary(
        model_name=model_name,
        avg_field_accuracy=round(sum(r.field_accuracy for r in results) / n, 3),
        exact_match_rate=round(sum(r.exact_match for r in results) / n, 3),
        avg_latency_sec=round(sum(r.latency_sec for r in results) / n, 3),
        n_docs=n,
    )


def _normalize(value) -> str:
    return str(value).strip().lower() if value is not None else ""
>>>>>>> 22298f89189fd0a2a37213efc84616474a0cc990
