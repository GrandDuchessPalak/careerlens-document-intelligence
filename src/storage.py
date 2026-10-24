<<<<<<< HEAD
"""File-based storage: document (original) -> metadata -> json (extracted). Embeddings live in ChromaDB."""
import json
from pathlib import Path
from typing import List, Optional

import config
from .schemas import DocumentMetadata


class Storage:
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else config.STORAGE_DIR
        self.documents = self.root / "documents"
        self.metadata = self.root / "metadata"
        self.json = self.root / "json"
        for d in (self.documents, self.metadata, self.json):
            d.mkdir(parents=True, exist_ok=True)

    # originals
    def save_document(self, doc_id: str, version: int, data: bytes, suffix: str) -> Path:
        d = self.documents / doc_id
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"v{version}{suffix}"
        p.write_bytes(data)
        return p

    def document_path(self, doc_id: str, version: int) -> Path:
        matches = list((self.documents / doc_id).glob(f"v{version}.*"))
        if not matches:
            raise FileNotFoundError(f"{doc_id} v{version} not found")
        return matches[0]

    # metadata
    def save_metadata(self, meta: DocumentMetadata) -> None:
        d = self.metadata / meta.doc_id
        d.mkdir(parents=True, exist_ok=True)
        (d / f"v{meta.version}.json").write_text(meta.model_dump_json(indent=2))

    def load_metadata(self, doc_id: str, version: int) -> DocumentMetadata:
        p = self.metadata / doc_id / f"v{version}.json"
        if not p.exists():
            raise FileNotFoundError(f"{doc_id} v{version} not found")
        return DocumentMetadata.model_validate_json(p.read_text())

    def list_versions(self, doc_id: str) -> List[int]:
        d = self.metadata / doc_id
        if not d.exists():
            return []
        return sorted(int(p.stem[1:]) for p in d.glob("v*.json"))

    def list_doc_ids(self) -> List[str]:
        return sorted(p.name for p in self.metadata.iterdir() if p.is_dir())

    # extracted json
    def save_json(self, doc) -> Path:
        d = self.json / doc.doc_id
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"v{doc.version}.json"
        p.write_text(doc.model_dump_json(indent=2))
        return p

    def load_json(self, doc_id: str, version: int) -> dict:
        p = self.json / doc_id / f"v{version}.json"
        if not p.exists():
            raise FileNotFoundError(f"No extraction for {doc_id} v{version}")
        return json.loads(p.read_text())
=======
from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from config import get_settings
from schemas import DocumentType
from version_manager import next_version

logger = logging.getLogger(__name__)


class DocumentMetadata(BaseModel):
    doc_id: str
    version: str
    document_type: DocumentType
    uploaded_at: str
    extraction_model: Optional[str] = None
    original_filename: str


class StorageError(RuntimeError):
    pass


def save_upload(doc_id: str, src_path: str, original_filename: str, document_type: DocumentType) -> DocumentMetadata:
    settings = get_settings()
    version = next_version(doc_id)
    version_dir = Path(settings.docs_dir) / doc_id / version
    version_dir.mkdir(parents=True, exist_ok=True)

    dest = version_dir / Path(original_filename).name
    try:
        shutil.copy(src_path, dest)
    except OSError as exc:
        raise StorageError(f"Failed to save upload to {dest}: {exc}") from exc

    meta = DocumentMetadata(
        doc_id=doc_id,
        version=version,
        document_type=document_type,
        uploaded_at=datetime.now(timezone.utc).isoformat(),
        original_filename=original_filename,
    )
    _write_metadata(meta)
    return meta


def save_extraction(doc_id: str, version: str, extraction_model: str, parsed_json: dict) -> None:
    settings = get_settings()
    json_dir = Path(settings.json_dir) / doc_id
    json_dir.mkdir(parents=True, exist_ok=True)

    out_path = json_dir / f"{version}.json"
    out_path.write_text(json.dumps(parsed_json, indent=2))

    meta = load_metadata(doc_id, version)
    if meta:
        meta.extraction_model = extraction_model
        _write_metadata(meta)


def load_extraction(doc_id: str, version: str) -> dict:
    settings = get_settings()
    path = Path(settings.json_dir) / doc_id / f"{version}.json"
    if not path.exists():
        raise StorageError(f"No extraction found for {doc_id}/{version}")
    return json.loads(path.read_text())


def load_metadata(doc_id: str, version: str) -> Optional[DocumentMetadata]:
    settings = get_settings()
    path = Path(settings.meta_dir) / doc_id / f"{version}.json"
    if not path.exists():
        return None
    return DocumentMetadata.model_validate_json(path.read_text())


def _write_metadata(meta: DocumentMetadata) -> None:
    settings = get_settings()
    meta_dir = Path(settings.meta_dir) / meta.doc_id
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / f"{meta.version}.json").write_text(meta.model_dump_json(indent=2))
>>>>>>> 22298f89189fd0a2a37213efc84616474a0cc990
