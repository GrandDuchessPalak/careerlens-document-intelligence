import pytest
from src.utils import extract_json, to_float, slugify
from src.vector_store import json_to_chunks, chunk_text
from eval.metrics import score_document, aggregate, set_f1


def test_extract_json_handles_prose_and_fences():
    assert extract_json('Sure! ```json\n{"a": {"b": "}"}}\n``` done') == {"a": {"b": "}"}}
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_helpers():
    assert to_float("CGPA: 8.75/10") == 8.75 and to_float("n/a") is None
    assert slugify("My Resume (final).pdf") == "my_resume_final_pdf"


def test_chunks():
    doc = {"doc_id": "cv", "version": 1, "document_type": "resume", "fields": {
        "name": {"value": "Jane", "confidence": 1}, "email": {"value": None, "confidence": 0},
        "education": [{"degree": "BTech", "institution": "IGDTUW", "year": None, "confidence": 0.9}]}}
    ch = json_to_chunks(doc)
    assert len(ch) == 2 and "name: Jane" in ch[0] and "institution: IGDTUW" in ch[1]
    assert all(len(c) <= 1700 for c in chunk_text("a\n\n" + "word " * 1000))


def test_metrics():
    gold = {"issuer": "ABC Corp", "issue_date": "12 March 2026", "recipient_name": "Jane Doe"}
    pred = {"issuer": "abc corp.", "issue_date": "13 March 2026", "recipient_name": None}
    sc = score_document(pred, gold, ["issuer", "issue_date", "recipient_name"])
    agg = aggregate([sc])
    assert sc["fields"]["issuer"]["correct"] and not sc["fields"]["issue_date"]["correct"]
    assert agg["extraction_accuracy"] == pytest.approx(1 / 3) and agg["exact_match"] == 0
    assert agg["precision"] == pytest.approx(0.5) and agg["recall"] == pytest.approx(1 / 3)
    assert set_f1(["Python", "SQL"], ["python", "docker"]) == pytest.approx(0.5)
