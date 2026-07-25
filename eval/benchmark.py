from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from donut_extractor import extract_with_donut
from layoutlm_extractor import extract_with_layoutlm
from metrics import DocMetrics, score_document, summarize, time_extraction
from pdf_to_image import load_image, preprocess

logger = logging.getLogger(__name__)

# Expects data/annotated/{doc_id}.png + data/annotated/{doc_id}.json (ground truth)
ANNOTATED_DIR = Path("data/annotated")


def run_benchmark(document_type: str, model: str = "donut") -> None:
    results: List[DocMetrics] = []

    for gt_path in ANNOTATED_DIR.glob("*.json"):
        doc_id = gt_path.stem
        image_path = ANNOTATED_DIR / f"{doc_id}.png"
        if not image_path.exists():
            logger.warning("Skipping %s: no matching image", doc_id)
            continue

        ground_truth = json.loads(gt_path.read_text())
        image = preprocess(load_image(str(image_path)))

        def _extract():
            if model == "donut":
                return extract_with_donut(image, document_type).parsed_json
            elif model == "layoutlmv3":
                return extract_with_layoutlm(image, document_type).parsed_json
            raise ValueError(f"Unknown model: {model}")

        try:
            predicted, latency = time_extraction(_extract)
        except Exception as exc:  # noqa: BLE001
            logger.error("Extraction failed for %s: %s", doc_id, exc)
            continue

        exact_match, field_accuracy = score_document(predicted, ground_truth)
        results.append(DocMetrics(
            doc_id=doc_id, exact_match=exact_match,
            field_accuracy=field_accuracy, latency_sec=latency,
        ))

    if not results:
        logger.error("No documents scored — check data/annotated/ contents")
        return

    summary = summarize(results, model_name=model)
    print(summary.model_dump_json(indent=2))


if __name__ == "__main__":
    import sys
    doc_type = sys.argv[1] if len(sys.argv) > 1 else "resume"
    model_name = sys.argv[2] if len(sys.argv) > 2 else "donut"
    run_benchmark(doc_type, model_name)