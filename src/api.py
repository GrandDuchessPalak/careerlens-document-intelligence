"""All routes (contract frozen in the design spec). Run: uvicorn src.api:app --reload"""
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

import config
from .schemas import (ATSRequest, ATSResponse, DocType, DocumentMetadata, ModelName, QueryRequest,
                      QueryResponse, UploadResponse, VersionsResponse)
from .storage import Storage
from .utils import slugify
from .version_manager import VersionManager

app = FastAPI(title="CareerLens")
storage = Storage()
versions = VersionManager(storage)


def _resolve(doc_id: str, version: Optional[int]) -> int:
    try:
        return versions.resolve(doc_id, version)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.post("/documents/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...), doc_id: Optional[str] = Form(None)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in config.ALLOWED_SUFFIXES:
        raise HTTPException(400, f"Unsupported file type '{suffix}'")
    did = slugify(doc_id or Path(file.filename).stem)
    version = versions.next_version(did)
    storage.save_document(did, version, await file.read(), suffix)
    storage.save_metadata(DocumentMetadata(doc_id=did, version=version, filename=file.filename))
    return UploadResponse(doc_id=did, version=version)


@app.get("/documents/{doc_id}/versions", response_model=VersionsResponse)
def list_versions(doc_id: str):
    vs = storage.list_versions(doc_id)
    if not vs:
        raise HTTPException(404, f"Unknown document: {doc_id}")
    return VersionsResponse(doc_id=doc_id, versions=[storage.load_metadata(doc_id, v) for v in vs])


@app.post("/documents/{doc_id}/extract")
def extract(doc_id: str, version: Optional[int] = None, model: ModelName = ModelName.prompted_vlm,
            doc_type: Optional[DocType] = None):
    from . import pipeline          # heavy imports stay lazy
    v = _resolve(doc_id, version)
    try:
        doc = pipeline.process(storage, doc_id, v, model.value, doc_type.value if doc_type else None)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    return doc.model_dump(mode="json")


@app.get("/documents/{doc_id}/json")
def get_json(doc_id: str, version: Optional[int] = None):
    v = _resolve(doc_id, version)
    try:
        return storage.load_json(doc_id, v)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    from . import rag
    return rag.answer(req.question, req.doc_ids, req.top_k)


@app.post("/analysis/ats", response_model=ATSResponse)
def ats(req: ATSRequest):
    from .ats import ats_score
    v = _resolve(req.doc_id, req.version)
    try:
        data = storage.load_json(req.doc_id, v)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    if data["document_type"] != "resume":
        raise HTTPException(400, "ATS scoring only applies to resumes")
    return ats_score(data)
