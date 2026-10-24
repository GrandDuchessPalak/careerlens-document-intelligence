<<<<<<< HEAD
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
=======
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from config import get_settings
from doc_type_classifier import classify_document
from donut_extractor import extract_with_donut
from layoutlm_extractor import extract_with_layoutlm
from pdf_to_image import load_image, pdf_to_images, preprocess
from rag import answer_question
from schemas import DocumentType
from storage import load_extraction, save_extraction, save_upload
from vector_store import index_document
from version_manager import list_versions

logger = logging.getLogger(__name__)
app = FastAPI(title="CareerLens API")


class QueryRequest(BaseModel):
    question: str
    doc_id: str | None = None


@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    settings = get_settings()
    doc_id = Path(file.filename).stem

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        image = _load_first_page(tmp_path)
        classification = classify_document(image)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not process file: {exc}") from exc

    meta = save_upload(doc_id, tmp_path, file.filename, classification.document_type)
    return {"doc_id": doc_id, "version": meta.version, "document_type": classification.document_type}


@app.get("/documents/{doc_id}/versions")
async def get_versions(doc_id: str):
    versions = list_versions(doc_id)
    if not versions:
        raise HTTPException(status_code=404, detail="No versions found for this doc_id")
    return {"doc_id": doc_id, "versions": versions}


@app.post("/documents/{doc_id}/extract")
async def extract_document(doc_id: str, version: str, document_type: DocumentType, model: str = "donut"):
    settings = get_settings()
    file_path = Path(settings.docs_dir) / doc_id / version
    files = list(file_path.glob("*"))
    if not files:
        raise HTTPException(status_code=404, detail="Document not found")

    image = load_image(str(files[0]))
    image = preprocess(image)

    try:
        if model == "donut":
            result = extract_with_donut(image, document_type)
        elif model == "layoutlmv3":
            result = extract_with_layoutlm(image, document_type)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown model: {model}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {exc}") from exc

    save_extraction(doc_id, version, model, result.parsed_json)
    index_document(doc_id, version, str(result.parsed_json))
    return result.parsed_json


@app.get("/documents/{doc_id}/json")
async def get_extraction(doc_id: str, version: str):
    try:
        return load_extraction(doc_id, version)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/query")
async def query_documents(req: QueryRequest):
    try:
        result = answer_question(req.question, doc_id=req.doc_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result.model_dump()


def _load_first_page(path: str):
    if path.lower().endswith(".pdf"):
        images = pdf_to_images(path, out_dir=tempfile.mkdtemp())
        return load_image(images[0])
    return load_image(path)
>>>>>>> 22298f89189fd0a2a37213efc84616474a0cc990
