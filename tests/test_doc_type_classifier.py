from PIL import Image

from src.doc_type_classifier import classify_document


def test_confident_resume_uses_rvlcdip():
    image = Image.new("RGB", (100, 100))

    def fake_rvlcdip(_image):
        return "resume", 0.95

    def fake_vlm(_image, _prompt):
        raise AssertionError("VLM should not be called")

    result = classify_document(
        image,
        rvlcdip_fn=fake_rvlcdip,
        vlm_fn=fake_vlm,
    )

    assert result.document_type == "resume"
    assert result.source == "rvlcdip"
    assert result.confidence == 0.95


def test_non_resume_falls_back_to_vlm():
    image = Image.new("RGB", (100, 100))

    def fake_rvlcdip(_image):
        return "letter", 0.90

    def fake_vlm(_image, _prompt):
        return '{"document_type": "certificate", "confidence": 0.88}'

    result = classify_document(
        image,
        rvlcdip_fn=fake_rvlcdip,
        vlm_fn=fake_vlm,
    )

    assert result.document_type == "certificate"
    assert result.source == "vlm"
    assert result.confidence == 0.88


def test_low_confidence_resume_falls_back():
    image = Image.new("RGB", (100, 100))

    def fake_rvlcdip(_image):
        return "resume", 0.40

    def fake_vlm(_image, _prompt):
        return '{"document_type": "transcript", "confidence": 0.91}'

    result = classify_document(
        image,
        rvlcdip_fn=fake_rvlcdip,
        vlm_fn=fake_vlm,
    )

    assert result.document_type == "transcript"
    assert result.source == "vlm"