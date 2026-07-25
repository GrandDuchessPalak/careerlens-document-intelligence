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