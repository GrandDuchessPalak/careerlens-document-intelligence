"""Turn eval/results/results.json into figures for the README and report.

Usage (from project root, after python -m eval.benchmark):
    python -m eval.plot_results
Outputs PNG files to docs/figures/.
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLORS = ["#2b6cb0", "#dd6b20", "#2f855a", "#805ad5", "#c53030"]


def grouped_bar(ax, categories, series, ylabel, ylim=None):
    """series: {label: [value per category]}"""
    n = max(len(series), 1)
    width = 0.8 / n
    for i, (label, vals) in enumerate(series.items()):
        xs = [c + (i - (n - 1) / 2) * width for c in range(len(categories))]
        bars = ax.bar(xs, vals, width, label=label, color=COLORS[i % len(COLORS)])
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{v:.2f}",
                    ha="center", va="bottom", fontsize=8)
    ax.set_xticks(range(len(categories)))
    ax.set_xticklabels(categories, rotation=20, ha="right")
    ax.set_ylabel(ylabel)
    if ylim:
        ax.set_ylim(*ylim)
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(frameon=False)


def save(fig, out: Path, name: str):
    fig.tight_layout()
    path = out / name
    fig.savefig(path, dpi=160)
    plt.close(fig)
    print("wrote", path)


def main(results_path: Path, out: Path):
    res = json.loads(results_path.read_text())
    out.mkdir(parents=True, exist_ok=True)
    models = list(res)

    # 1. overall quality metrics
    metrics = [("extraction_accuracy", "accuracy"), ("exact_match", "exact match"),
               ("precision", "precision"), ("recall", "recall"), ("f1", "F1")]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    grouped_bar(ax, [m[1] for m in metrics],
                {m: [res[m].get(k, 0) for k, _ in metrics] for m in models}, "score", (0, 1.1))
    ax.set_title("Overall extraction quality by model")
    save(fig, out, "overall_metrics.png")

    # 2. per-field accuracy
    fields = sorted({f for m in models for f in res[m].get("field_accuracy", {})})
    if fields:
        fig, ax = plt.subplots(figsize=(9, 4.5))
        grouped_bar(ax, fields, {m: [res[m]["field_accuracy"].get(f, 0) for f in fields] for m in models},
                    "accuracy", (0, 1.1))
        ax.set_title("Per-field accuracy")
        save(fig, out, "field_accuracy.png")

    # 3. latency and memory
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
    grouped_bar(a1, ["latency"], {m: [res[m].get("avg_latency_s", 0)] for m in models}, "seconds per document")
    a1.set_title("Average latency")
    grouped_bar(a2, ["RSS (CPU RAM)", "peak GPU"],
                {m: [res[m].get("rss_mb", 0), res[m].get("peak_gpu_mb", 0)] for m in models}, "MB")
    a2.set_title("Memory")
    save(fig, out, "latency_memory.png")

    # 4. accuracy by document tag (error analysis)
    tags = sorted({t for m in models for t in res[m].get("accuracy_by_tag", {})})
    if tags:
        fig, ax = plt.subplots(figsize=(9, 4.5))
        grouped_bar(ax, tags, {m: [res[m]["accuracy_by_tag"].get(t, 0) for t in tags] for m in models},
                    "accuracy", (0, 1.1))
        ax.set_title("Accuracy by document condition")
        save(fig, out, "accuracy_by_tag.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="eval/results/results.json")
    ap.add_argument("--out", default="docs/figures")
    a = ap.parse_args()
    main(Path(a.results), Path(a.out))