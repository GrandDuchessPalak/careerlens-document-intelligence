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