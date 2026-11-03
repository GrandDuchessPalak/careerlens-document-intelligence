"""ChromaDB persistent vector store. Chunks come from the extracted JSON (one line per field/entry)
plus raw OCR text."""
import re
from typing import List, Optional

import config


def json_to_chunks(doc: dict) -> List[str]:
    head = f"{doc['document_type']} {doc['doc_id']} v{doc['version']}"
    chunks = []
    for key, val in doc["fields"].items():
        if isinstance(val, dict) and "value" in val:
            if val["value"] not in (None, "", []):
                chunks.append(f"{head} | {key}: {val['value']}")
        elif isinstance(val, list):
            for entry in val:
                parts = ", ".join(f"{k}: {v}" for k, v in entry.items() if k != "confidence" and v)
                if parts:
                    chunks.append(f"{head} | {key}: {parts}")
    return chunks


def chunk_text(text: str, size: int = config.CHUNK_CHARS) -> List[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if cur and len(cur) + len(p) > size:
            chunks.append(cur)
            cur = ""
        cur = f"{cur}\n{p}".strip()
        while len(cur) > size * 2:           # very long paragraph
            chunks.append(cur[:size])
            cur = cur[size:]
    if cur:
        chunks.append(cur)
    return chunks


class VectorStore:
    def __init__(self, path=None):
        import chromadb
        from chromadb.utils import embedding_functions
        config.EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(path or config.EMBEDDINGS_DIR))
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=config.EMBEDDING_MODEL)
        self.col = client.get_or_create_collection("careerlens", embedding_function=ef,
                                                   metadata={"hnsw:space": "cosine"})

    def index_document(self, doc: dict, raw_text: str = "") -> int:
        did, ver = doc["doc_id"], doc["version"]
        self.col.delete(where={"$and": [{"doc_id": did}, {"version": ver}]})
        items = [("json", t) for t in json_to_chunks(doc)] + [("ocr", t) for t in chunk_text(raw_text)]
        if not items:
            return 0
        self.col.upsert(
            ids=[f"{did}:v{ver}:{src}:{i}" for i, (src, _) in enumerate(items)],
            documents=[f"{doc['document_type']} {did} v{ver} | {t}" if src == "ocr" else t for src, t in items],
            metadatas=[{"doc_id": did, "version": ver, "document_type": doc["document_type"], "source": src}
                       for src, _ in items])
        return len(items)

    def query(self, question: str, k: int = config.TOP_K, doc_ids: Optional[List[str]] = None) -> List[dict]:
        where = {"doc_id": {"$in": doc_ids}} if doc_ids else None
        res = self.col.query(query_texts=[question], n_results=k, where=where)
        return [{"text": t, "metadata": m, "distance": d}
                for t, m, d in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])]
