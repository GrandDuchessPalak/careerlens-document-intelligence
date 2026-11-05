"""Benchmark Donut vs LayoutLM vs prompted VLM on the hand-annotated set, with error analysis.

Usage (from project root):
  python -m eval.benchmark --models donut layoutlmv3 prompted_vlm
Annotated file format: see data/annotated/example_certificate.json
Outputs: eval/results/{results.json, results.md, errors.jsonl}
"""
import argparse, json, time
from collections import defaultdict
from pathlib import Path

import config
from src import pdf_to_image
from src.pipeline import get_extractor
from src.schemas import FIELDS_MODEL, SCALAR_FIELDS
from .metrics import aggregate, score_document


def load_annotated(folder: Path):
    samples = []
    for p in sorted(folder.glob("*.json")):
        s = json.loads(p.read_text())
        if s.get("_example"):
            continue
        s["_file"] = p.name
        samples.append(s)
    return samples


def plain(fields: dict) -> dict:
    """{'name': {'value':..,'confidence':..}, 'education': [...]} -> {'name': value, 'education': [...]}."""
    return {k: (v["value"] if isinstance(v, dict) and "value" in v else v) for k, v in fields.items()}


def _mem():
    import psutil
    mb = psutil.Process().memory_info().rss / 2**20
    try:
        import torch
        gpu = torch.cuda.max_memory_allocated() / 2**20 if torch.cuda.is_available() else 0.0
    except ImportError:
        gpu = 0.0
    return mb, gpu


def run(models, folder: Path, out: Path):
    samples = load_annotated(folder)
    if not samples:
        raise SystemExit(f"No annotated samples in {folder} (see README: hand-annotate 20-40 documents).")
    out.mkdir(parents=True, exist_ok=True)
    results, errors = {}, []
    for m in models:
        ext = get_extractor(m)
        scores, lat, tag_scores = [], [], defaultdict(list)
        for s in samples:
            images = pdf_to_image.prepare(config.ROOT / s["image"])
            t0 = time.perf_counter()
            try:
                fields = ext.extract(images, s["document_type"])
            except Exception as e:
                fields = {}
                errors.append({"model": m, "file": s["_file"], "error": str(e)[:300], "tags": s.get("tags", [])})
            lat.append(time.perf_counter() - t0)
            doc_type = s["document_type"]
            sc = score_document(plain(FIELDS_MODEL[doc_type].model_validate(fields).model_dump()),
                                s["fields"], SCALAR_FIELDS[doc_type])
            scores.append(sc)
            for t in s.get("tags", []):
                tag_scores[t].append(sc)
            for f, r in sc["fields"].items():
                if r["gold_present"] and not r["correct"]:
                    errors.append({"model": m, "file": s["_file"], "field": f, "gold": r["gold"],
                                   "pred": r["pred"], "tags": s.get("tags", [])})
        rss, gpu = _mem()
        agg = aggregate(scores)
        agg["avg_latency_s"] = sum(lat) / len(lat)
        agg["rss_mb"], agg["peak_gpu_mb"] = round(rss), round(gpu)
        agg["accuracy_by_tag"] = {t: aggregate(v)["extraction_accuracy"] for t, v in tag_scores.items()}
        results[m] = agg

    (out / "results.json").write_text(json.dumps(results, indent=2))
    (out / "errors.jsonl").write_text("\n".join(json.dumps(e) for e in errors))
    rows = ["| model | accuracy | exact match | precision | recall | F1 | latency (s/doc) | RSS MB | GPU MB |",
            "|---|---|---|---|---|---|---|---|---|"]
    for m, a in results.items():
        rows.append(f"| {m} | {a['extraction_accuracy']:.3f} | {a['exact_match']:.3f} | {a['precision']:.3f} | "
                    f"{a['recall']:.3f} | {a['f1']:.3f} | {a['avg_latency_s']:.2f} | {a['rss_mb']} | {a['peak_gpu_mb']} |")
    (out / "results.md").write_text("\n".join(rows))
    print("\n".join(rows))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["donut", "layoutlmv3", "prompted_vlm"])
    ap.add_argument("--annotated", default=str(config.ANNOTATED_DIR))
    ap.add_argument("--out", default=str(config.ROOT / "eval" / "results"))
    a = ap.parse_args()
    run(a.models, Path(a.annotated), Path(a.out))
