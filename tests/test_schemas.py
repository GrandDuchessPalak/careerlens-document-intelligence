from datetime import datetime

import pytest
from pydantic import ValidationError

from src.schemas import ConfidentValue, parse_document


def test_confident_value():
    value = ConfidentValue[str](value="Akshita", confidence=0.9)

    assert value.value == "Akshita"
    assert value.confidence == 0.9


def test_invalid_confidence():
    with pytest.raises(ValidationError):
        ConfidentValue[str](value="test", confidence=1.5)


def test_parse_resume():
    data = {
        "doc_id": "doc-1",
        "version": 1,
        "document_type": "resume",
        "extraction_model": "donut",
        "extracted_at": datetime.now(),
        "fields": {
            "name": {"value": "Test User", "confidence": 0.95},
            "email": {"value": "test@example.com", "confidence": 0.9},
            "phone": {"value": "1234567890", "confidence": 0.8},
            "skills": {"value": ["Python", "ML"], "confidence": 0.9},
            "education": [],
            "experience": [],
            "projects": [],
        },
    }

    document = parse_document("resume", data)

    assert document.document_type == "resume"
    assert document.fields.name.value == "Test User"