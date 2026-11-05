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
