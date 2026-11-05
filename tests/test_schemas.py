import pytest
from pydantic import ValidationError
from src.schemas import build_doc, parse_extraction, schema_example, SCALAR_FIELDS, FIELDS_MODEL


def test_defaults_fill_missing_fields():
    d = build_doc("cv", 1, "resume", "donut", {"name": {"value": "Jane", "confidence": 0.9}})
    assert d.fields.name.value == "Jane"
    assert d.fields.email.confidence == 0.0 and d.fields.education == []


def test_confidence_bounds():
    with pytest.raises(ValidationError):
        build_doc("cv", 1, "resume", "donut", {"name": {"value": "x", "confidence": 1.5}})


def test_discriminator_and_enum():
    d = parse_extraction({"doc_id": "t", "version": 2, "document_type": "transcript",
                          "extraction_model": "layoutlmv3", "fields": {"cgpa": {"value": 8.7, "confidence": 0.8}}})
    assert d.document_type == "transcript" and d.fields.cgpa.value == 8.7
    with pytest.raises(ValidationError):
        build_doc("t", 1, "transcript", "gpt", {})


def test_schema_example_has_entries_and_scalar_fields_exist():
    ex = schema_example("resume")
    assert isinstance(ex["education"], list) and "institution" in ex["education"][0]
    for t, names in SCALAR_FIELDS.items():
        for n in names:
            assert n in FIELDS_MODEL[t].model_fields
