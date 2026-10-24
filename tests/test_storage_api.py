import importlib
from fastapi.testclient import TestClient


def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    import config, src.api as api
    importlib.reload(config)
    importlib.reload(api)
    return TestClient(api.app), api


def test_upload_versions_and_json(tmp_path, monkeypatch):
    c, api = make_client(tmp_path, monkeypatch)
    r1 = c.post("/documents/upload", files={"file": ("My Resume.pdf", b"%PDF-1.4")})
    r2 = c.post("/documents/upload", files={"file": ("My Resume.pdf", b"%PDF-1.4 v2")})
    assert r1.json() == {"doc_id": "my_resume", "version": 1}
    assert r2.json()["version"] == 2
    vs = c.get("/documents/my_resume/versions").json()["versions"]
    assert [v["version"] for v in vs] == [1, 2]
    assert c.get("/documents/my_resume/json").status_code == 404      # not extracted yet
    assert c.get("/documents/nope/versions").status_code == 404
    assert c.post("/documents/upload", files={"file": ("x.exe", b"x")}).status_code == 400


def test_json_roundtrip_and_ats(tmp_path, monkeypatch):
    c, api = make_client(tmp_path, monkeypatch)
    c.post("/documents/upload", files={"file": ("cv.pdf", b"%PDF")})
    from src.schemas import build_doc
    doc = build_doc("cv", 1, "resume", "prompted_vlm", {
        "name": {"value": "Jane", "confidence": 0.9}, "skills": {"value": ["python"], "confidence": 0.8}})
    api.storage.save_json(doc)
    assert c.get("/documents/cv/json").json()["fields"]["name"]["value"] == "Jane"
    ats = c.post("/analysis/ats", json={"doc_id": "cv"}).json()
    assert ats["ats_score"] < 100 and "missing email" in ats["reasons"]
